import asyncio
import base64
import json
import websockets
import wave
import io
from collections import deque
from pipecat.processors.frameworks.rtvi import RTVIProcessor, RTVIServerMessageFrame, RTVIConfig
from pipecat.frames.frames import InputAudioRawFrame, StartFrame, CancelFrame, EndFrame, UserStartedSpeakingFrame, UserStoppedSpeakingFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from loguru import logger

class HumeOfflineWebSocketProcessor():
    def __init__(self, api_key: str, buffer_threshold_ms: int = 500, sample_rate: int = 16000, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key
        self.rtvi = None
        self.websocket = None
        self.process_task = None
        self.process_frames = False
        
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

    def set_rtvi(self, rtvi):
        self.rtvi = rtvi

    async def start(self, frame: StartFrame):
        """Establish WebSocket connection to Hume's API."""
        headers = {"X-Hume-Api-Key": self.api_key}
        self.websocket = await websockets.connect(
            "wss://api.hume.ai/v0/stream/models",
            extra_headers=headers
        )
        # Configure Hume to use the prosody model for emotion analysis
        await self.websocket.send(json.dumps({"models": {"prosody": {}}}))
        
        self.running = True
        self.process_task = asyncio.create_task(self._process_task())
        logger.info("Started Hume WebSocket processor")

    async def process_frame(self, frame, direction):        
        if isinstance(frame, StartFrame):
            logger.info("Starting Hume WebSocket connection")
            await self.start(frame)
        elif isinstance(frame, UserStartedSpeakingFrame):
            logger.info("User started speaking")
            self.process_frames = True
            # Track user started speaking
            if self.rtvi and hasattr(self.rtvi, "flow_manager") and self.rtvi.flow_manager:
                self.rtvi.flow_manager.state["user_started_speaking"] = True
                self.rtvi.flow_manager.state["emotions_fully_processed"] = False
        elif isinstance(frame, UserStoppedSpeakingFrame):
            logger.info("User stopped speaking")
            self.process_frames = False
            # Optionally, you may want to reset user_started_speaking here, or keep it until next start

        if self.process_frames and direction == FrameDirection.DOWNSTREAM and isinstance(frame, InputAudioRawFrame):
            #logger.info(f"Processing frame: {frame} direction: {direction}")
            # Instead of sending immediately, add to buffer
            async with self.buffer_lock:
                self.audio_buffer.append(frame.audio)
                self.buffer_event.set()  # Signal that data is available
            
        if isinstance(frame, (CancelFrame, EndFrame)):
            logger.info("Stopping Hume WebSocket connection")
            await self.stop()

    async def _process_task(self):
        """Monitor buffer size and send data when threshold is reached."""
        while self.running:
            try:
                # After user stopped speaking and buffer empty, mark emotions fully processed
                #if not self.process_frames:
                #    async with self.buffer_lock:
                #        if not self.audio_buffer:
                #            logger.info("Buffer empty, marking emotions fully processed")
                #            self.rtvi.flow_manager.state["emotions_fully_processed"] = True
                
                # Wait for data to be available in the buffer
                await self.buffer_event.wait()
                
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
                                logger.info("User stopped speaking : marking emotions fully processed")
                                self.rtvi.flow_manager.state["emotions_fully_processed"] = True
                    
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
                        await self.websocket.send(json.dumps(message))

                        # Receive and process response
                        response = await self.websocket.recv()
                        emotion_data = json.loads(response)
  
                        # Check for error, safely accessing the key
                        if emotion_data.get('error'):
                            logger.warning(f"Error from Hume: {emotion_data.get('error')}")
                            continue

                        # Safely check prosody data
                        prosody_data = emotion_data.get('prosody', {})
                        if prosody_data and prosody_data.get('warning'):
                            logger.warning(f"Hume warning: {prosody_data.get('warning')}")
                                
                        # Update flow manager state with raw emotions and a human-readable summary
                        if self.rtvi and hasattr(self.rtvi, "flow_manager") and self.rtvi.flow_manager:
                            try:
                                # store full emotion data
                                self.rtvi.flow_manager.state["emotion"] = emotion_data
                                
                                #check if we actually have some predictions
                                preds = emotion_data.get("prosody", {}).get("predictions", [])
                                if preds:
                                    # build summary of top 2 emotions by score
                                    try:
                                        ems = preds[0].get("emotions", [])
                                        top2 = sorted(ems, key=lambda e: e.get("score", 0), reverse=True)[:2]
                                        names = [e.get("name", "") for e in top2]
                                        summary = " and ".join(names)
                                        logger.info(f"Emotion summary: {summary}")
                                        self.rtvi.flow_manager.state["emotions_summary"] = summary
                                        logger.info(f"Hume emotion summary: {summary}")
                                    except Exception as e:
                                        logger.error(f"Error processing emotion data: {e}")

                                    # Create a custom message for the client
                                    message = {
                                        "emotion": emotion_data
                                    }
                                    status_frame = RTVIServerMessageFrame(message)
                                    await self.rtvi.queue_frame(status_frame)   

                            except Exception as e:
                                logger.error(f"Failed to update flow_manager state with emotions: {e}")
                        


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

    async def stop(self):
        """Clean up resources."""
        self.running = False
        if self.process_task:
            self.process_task.cancel()
            try:
                await self.process_task
            except asyncio.CancelledError:
                pass
        
        if self.websocket:
            await self.websocket.close()
        
        # Clear buffer
        async with self.buffer_lock:
            self.audio_buffer.clear()
            self.buffer_event.clear()
