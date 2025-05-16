import asyncio
import base64
import json
import websockets
import wave
import io
from collections import deque
from pipecat.processors.frameworks.rtvi import RTVIProcessor, RTVIServerMessageFrame
from pipecat.frames.frames import Frame, InputAudioRawFrame, StartFrame, CancelFrame, EndFrame, UserStartedSpeakingFrame, UserStoppedSpeakingFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.observers.base_observer import BaseObserver
from pipecat.utils.base_object import BaseObject
from loguru import logger

class HumeOfflineWebSocketObserver(BaseObserver, BaseObject):
    def __init__(self, api_key: str, rtvi: RTVIProcessor, buffer_threshold_ms: int = 500, sample_rate: int = 16000):
        super().__init__()
        self.api_key = api_key
        self.rtvi = rtvi
        
        # WebSocket connections for both models
        self.prosody_websocket = None
        self.language_websocket = None
        
        self.process_task = None
        self.process_frames = False
        self._frames_seen = set()
        
        # Initialize the accumulated emotional data state
        self.accumulated_emotions = {}
        # Count of emotion updates received - used for weighted averaging
        self.emotion_update_count = 0
        # Alpha parameter for exponential weighted average (0.7 gives good weight to recent emotions)
        self.alpha = 0.7
        
        # For storing language model emotions
        self.accumulated_language_emotions = {}
        # Queue for pending text transcriptions to process
        self.text_queue = asyncio.Queue()
        
        self._register_event_handler("on_start_processing_emotions")
        self._register_event_handler("on_emotions_received")
        self._register_event_handler("on_language_emotions_received")

        # Audio buffer configuration
        self.buffer_threshold_ms = buffer_threshold_ms
        self.sample_rate = sample_rate
        self.bytes_per_sample = 2  # assuming 16-bit audio
        self.num_channels = 1
        self.buffer_threshold_bytes = int(self.sample_rate * self.buffer_threshold_ms / 1000 * self.bytes_per_sample)
        
        # Buffer for storing audio data
        self.audio_buffer = deque()
        self.buffer_lock = asyncio.Lock()  # async lock for buffer access
        self.buffer_event = asyncio.Event()  # to signal when data is available
        
        # Processing state
        self.running = False
        self.bot_speaking = False

    async def start_hume(self, frame: StartFrame):
        """Establish WebSocket connections to Hume's API for both prosody and language models."""
        headers = {"X-Hume-Api-Key": self.api_key}
        
        # Connect to prosody model WebSocket
        self.prosody_websocket = await websockets.connect(
            "wss://api.hume.ai/v0/stream/models",
            extra_headers=headers
        )
        # Configure WebSocket to use the prosody model
        await self.prosody_websocket.send(json.dumps({"models": {"prosody": {}}}))
        response = await self.prosody_websocket.recv()
        logger.info("Connected to Hume prosody model WebSocket : " + response)
        
        # Connect to language model WebSocket
        self.language_websocket = await websockets.connect(
            "wss://api.hume.ai/v0/stream/models",
            extra_headers=headers
        )
        # Configure WebSocket to use the language model
        await self.language_websocket.send(json.dumps({"models": {"language": {"granularity": "passage"}}}))
        response = await self.language_websocket.recv()
        logger.info("Connected to Hume language model WebSocket : " + response)
        
        self.running = True
        self.process_task = asyncio.create_task(self._process_task())
        logger.info("Started Hume WebSocket processor")

    async def on_push_frame(
        self,
        src: FrameProcessor,
        dst: FrameProcessor,
        frame: Frame,
        direction: FrameDirection,
        timestamp: int,
    ):
        if frame.id in self._frames_seen:
            return
        self._frames_seen.add(frame.id)
        if isinstance(frame, StartFrame):
            logger.info("Starting Hume WebSocket connection")
            await self.start_hume(frame)
        elif isinstance(frame, BotStartedSpeakingFrame):
            logger.info("Bot started speaking")
            self.bot_speaking = True
        elif isinstance(frame, BotStoppedSpeakingFrame):
            logger.info("Bot stopped speaking")
            self.bot_speaking = False
        elif isinstance(frame, UserStartedSpeakingFrame):
            logger.info("User started speaking")
            if self.bot_speaking:
                logger.info("Bot is speaking, skipping user speaking")
                return
            self.process_frames = True
            # Reset accumulated emotions when user starts speaking
            self.accumulated_emotions = {}
            self.accumulated_language_emotions = {}
            # Reset emotion update counter
            self.emotion_update_count = 0
            await self._call_event_handler("on_start_processing_emotions")
        elif isinstance(frame, UserStoppedSpeakingFrame):
            logger.info("User stopped speaking")
            self.process_frames = False
            # Optionally, you may want to reset user_started_speaking here, or keep it until next start
        elif isinstance(frame, TranscriptionFrame):
            logger.info(f"Transcription frame received: {frame}")
            if frame.text:
                logger.info(f"Transcription: {frame.text}")
                # Add transcription to the queue for processing by the websocket thread
                await self.text_queue.put(frame.text)

        if self.process_frames and direction == FrameDirection.DOWNSTREAM and isinstance(frame, InputAudioRawFrame):
            #logger.info(f"Processing frame: {frame} direction: {direction}")
            # Instead of sending immediately, add to buffer
            async with self.buffer_lock:
                self.audio_buffer.append(frame.audio)
                self.buffer_event.set()  # Signal that data is available
            
        if isinstance(frame, (CancelFrame, EndFrame)):
            logger.info("Stopping Hume WebSocket connection")
            await self.stop_hume()

    async def _process_task(self):
        """Monitor buffer size and send data when threshold is reached."""
        while self.running:
            try:
                # Process any pending text transcriptions in the queue
                while not self.text_queue.empty():
                    text = await self.text_queue.get()
                    await self._process_text(text)
                    self.text_queue.task_done()
                
                # Use a timeout to prevent indefinite blocking on the buffer_event.wait()
                # This allows us to regularly check the text queue even if no audio is coming in
                try:
                    # Only wait up to 0.5 seconds for audio data
                    await asyncio.wait_for(self.buffer_event.wait(), timeout=0.3)
                except asyncio.TimeoutError:
                    # No audio data available within timeout, continue to next iteration
                    # This ensures we can still process text in the queue
                    continue
                
                # Calculate current buffer size
                buffer_size = 0
                async with self.buffer_lock:
                    for chunk in self.audio_buffer:
                        buffer_size += len(chunk)
                
                # If we have enough data, process it or if user stopped speaking then process all remaining data
                if buffer_size >= self.buffer_threshold_bytes or not self.process_frames:
                    # Collect audio data from buffer up to threshold
                    audio_data = bytearray()
                    collected_size = 0
                    
                    async with self.buffer_lock:
                        while self.audio_buffer and (collected_size < self.buffer_threshold_bytes or not self.process_frames):
                            chunk = self.audio_buffer.popleft()
                            audio_data.extend(chunk)
                            collected_size += len(chunk)
                        
                        # Reset event if buffer is empty
                        if not self.audio_buffer:
                            logger.info("Audio buffer empty")
                            self.buffer_event.clear()
                            if not self.process_frames:
                                # make sure we have emotions to send
                                if self.accumulated_emotions:
                                    logger.info("User stopped speaking : marking emotions fully processed")
                                    # Convert accumulated emotions back to the expected format for the event
                                    accumulated_prosody_data = {
                                        'prosody': {
                                            'predictions': [{
                                                'emotions': [
                                                {'name': name, 'score': score} 
                                                for name, score in self.accumulated_emotions.items()
                                            ]
                                            }]
                                        }
                                    }
                                    
                                    # Trigger event with accumulated emotion data
                                    await self._call_event_handler("on_emotions_received", accumulated_prosody_data)    
                                
                    
                    # Send collected audio to Hume
                    if audio_data and self.rtvi:

                        # Create WAV file in memory
                        wav_io = io.BytesIO()
                        with wave.open(wav_io, 'wb') as wav_file:
                            wav_file.setnchannels(self.num_channels)
                            wav_file.setsampwidth(self.bytes_per_sample)
                            wav_file.setframerate(self.sample_rate)
                            wav_file.writeframes(audio_data)

                        # Encode WAV data to base64
                        wav_data = wav_io.getvalue()
                        audio_b64 = base64.b64encode(wav_data).decode('utf-8')
                        message = {
                            "data": audio_b64,
                            "models": {"prosody": {}}
                        }
                        
                        # Use the prosody websocket for audio processing
                        await self.prosody_websocket.send(json.dumps(message))

                        # Receive and process response
                        response = await self.prosody_websocket.recv()
                        emotion_data = json.loads(response)
  
                        # Check for error, safely accessing the key
                        if emotion_data.get('error'):
                            logger.warning(f"Error from Hume: {emotion_data.get('error')}")
                            continue

                        # Safely check prosody data
                        prosody_data = emotion_data.get('prosody', {})
                        if prosody_data and prosody_data.get('warning'):
                            logger.warning(f"Hume warning: {prosody_data.get('warning')}")
                            
                        # Process and accumulate emotional data if it exists
                        if prosody_data and 'predictions' in prosody_data:
                            # Increment our update counter
                            self.emotion_update_count += 1
                            
                            for prediction in prosody_data.get('predictions', []):
                                for emotion in prediction.get('emotions', []):
                                    emotion_name = emotion.get('name')
                                    emotion_score = emotion.get('score', 0.0)
                                    
                                    # Calculate exponential weighted average to keep scores between 0 and 1
                                    if emotion_name in self.accumulated_emotions:
                                        # Use exponential weighted average: new_avg = alpha * current + (1-alpha) * prev_avg
                                        prev_score = self.accumulated_emotions[emotion_name]
                                        updated_score = self.alpha * emotion_score + (1 - self.alpha) * prev_score
                                        self.accumulated_emotions[emotion_name] = updated_score
                                    else:
                                        # First time seeing this emotion
                                        self.accumulated_emotions[emotion_name] = emotion_score
                                        
                else:
                    # Not enough data yet, wait a bit
                    await asyncio.sleep(0.1)
                    
            except websockets.ConnectionClosed:
                logger.error("Hume WebSocket connection closed.")
                break
            except Exception as e:
                logger.error(f"Error in hume process task: {e}")
                # Don't break the loop on error, just continue

        logger.info("Process task stopped")

    async def _process_text(self, text):
        """Process transcription text with Hume language model."""
        if not self.language_websocket or not text:
            return
        
        try:
            # Create message for language model analysis
            message = {
                "models": {"language": {"granularity": "passage"}},
                "raw_text": True,
                "data": text
            }
            
            # Send message to Hume API using the language websocket
            await self.language_websocket.send(json.dumps(message))
            
            # Receive and process response
            response = await self.language_websocket.recv()
            language_data = json.loads(response)
            #logger.info(f"Language data received: {language_data}")
            
            # Check for error
            if language_data.get('error'):
                logger.warning(f"Error from Hume language model: {language_data.get('error')}")
                return
                
            # Process language emotions - with passage granularity, emotions are already for the entire text
            language_predictions = language_data.get('language', {}).get('predictions', [])
            
            if language_predictions and len(language_predictions) > 0:
                # Get emotions from the passage-level prediction
                passage_emotions = language_predictions[0].get('emotions', [])
                
                # Use these emotions directly without additional processing
                # Since we're using passage granularity, we get one prediction for the entire text
                language_emotions_data = {
                    'language': {
                        'predictions': language_predictions,
                        'accumulated_emotions': passage_emotions
                    }
                }
            
            # Trigger event with language emotion data
            await self._call_event_handler("on_language_emotions_received", language_emotions_data)
            
        except Exception as e:
            logger.error(f"Error processing text with Hume language model: {e}")
    
    async def stop_hume(self):
        """Clean up resources."""
        self.running = False
        if self.process_task:
            self.process_task.cancel()
            try:
                await self.process_task
            except asyncio.CancelledError:
                pass
        
        # Close both websocket connections
        if self.prosody_websocket:
            await self.prosody_websocket.close()
            
        if self.language_websocket:
            await self.language_websocket.close()
            
        # Clear text queue
        while not self.text_queue.empty():
            try:
                self.text_queue.get_nowait()
                self.text_queue.task_done()
            except asyncio.QueueEmpty:
                break

        # Clear buffer
        async with self.buffer_lock:
            self.audio_buffer.clear()
            self.buffer_event.clear()
