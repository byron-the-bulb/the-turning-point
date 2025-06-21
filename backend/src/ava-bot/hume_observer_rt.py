import asyncio
import base64
import json
import websockets
import wave
import io
import aiohttp
import numpy as np
import time
import typing
from PIL import Image
from collections import deque
from pipecat.processors.frameworks.rtvi import RTVIProcessor, RTVIServerMessageFrame
from pipecat.frames.frames import Frame, InputAudioRawFrame, StartFrame, CancelFrame, EndFrame, UserStartedSpeakingFrame, UserStoppedSpeakingFrame, TranscriptionFrame, BotStartedSpeakingFrame, BotStoppedSpeakingFrame, ImageRawFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.observers.base_observer import BaseObserver, FramePushed
from pipecat.utils.base_object import BaseObject
from loguru import logger
from datetime import datetime, timezone
import aiohttp
from dataclasses import dataclass

@dataclass
class ImageFrameWithTimestamp:
    """Class to store image frame with timestamp"""
    frame: typing.Any
    timestamp: str

class HumeObserver(BaseObserver, BaseObject):
    def __init__(self, api_key: str, buffer_threshold_ms: int = 500, sample_rate: int = 16000):
        super().__init__()
        self.api_key = api_key

        # WebSocket connections for both models
        self.prosody_websocket = None
        self.language_websocket = None
        self.face_websocket = None
        
        self.process_task = None
        self.process_video_task = None
        self.process_frames = False
        self._frames_seen = set()
        self.bot_is_speaking = False
        
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
        
        # Queue for pending image frames to process
        self.image_queue = asyncio.Queue()
        # Flag to track whether we're processing video
        self.process_video = False
        
        self._register_event_handler("on_start_processing_emotions")
        self._register_event_handler("on_emotions_received")
        self._register_event_handler("on_bot_started_speaking")
        self._register_event_handler("on_bot_stopped_speaking")
        self._register_event_handler("on_face_emotions_received")
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
        
        # Session ID for facial data API (will be fetched dynamically)
        self.facial_data_session_id = None
        # Flag to avoid querying session ID too frequently
        self.last_session_id_query_time = 0
        # How often to refresh session ID (in seconds)
        self.session_id_refresh_interval = 60
        
        # Frame counter for facial data
        self.facial_frame_counter = 0

    async def _connect_websocket_with_retry(self, model_name, model_config):
        """Connect to a Hume WebSocket with retry logic.
        
        Args:
            model_name: Name of the model (for logging)
            model_config: Configuration JSON for the model initialization
            
        Returns:
            The connected WebSocket client
        """
        headers = {"X-Hume-Api-Key": self.api_key}
        max_retries = 5
        base_delay = 1  # Starting delay in seconds
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Connecting to Hume {model_name} model WebSocket (attempt {attempt}/{max_retries})...")
                
                # Connect to the WebSocket
                websocket = await websockets.connect(
                    "wss://api.hume.ai/v0/stream/models",
                    extra_headers=headers,
                    open_timeout=20
                )
                
                # Configure WebSocket with the model
                await websocket.send(json.dumps({"models": model_config}))
                response = await websocket.recv()
                logger.info(f"Connected to Hume {model_name} model WebSocket: {response}")
                
                return websocket
                
            except (websockets.exceptions.WebSocketException, 
                    asyncio.TimeoutError, 
                    ConnectionError) as e:
                
                if attempt < max_retries:
                    # Calculate delay with exponential backoff
                    delay = base_delay * (2 ** (attempt - 1))  # 1, 2, 4, 8, 16 seconds...
                    logger.warning(f"Failed to connect to {model_name} WebSocket: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Failed to connect to {model_name} WebSocket after {max_retries} attempts: {e}")
                    raise
    
    async def _reconnect_websocket(self, websocket_attr, model_name, model_config):
        """Reconnect a specific WebSocket if it gets disconnected.
        
        Args:
            websocket_attr: The attribute name of the websocket (e.g., 'prosody_websocket')
            model_name: Name of the model (for logging)
            model_config: Configuration JSON for the model initialization
            
        Returns:
            bool: True if reconnection was successful
        """
        try:
            # Close the previous connection if it exists
            old_websocket = getattr(self, websocket_attr)
            if old_websocket:
                try:
                    await old_websocket.close()
                except Exception:
                    pass
            
            # Connect with retry
            new_websocket = await self._connect_websocket_with_retry(model_name, model_config)
            
            # Update the websocket attribute
            setattr(self, websocket_attr, new_websocket)
            return True
            
        except Exception as e:
            logger.error(f"Failed to reconnect {model_name} WebSocket: {e}")
            return False
    
    async def start_hume(self, frame: StartFrame):
        """Establish WebSocket connections to Hume's API for prosody, language, and face models."""
        logger.info("Starting WebSocket connections to Hume API")
        
        try:
            # Connect to all three models with retry logic
            self.prosody_websocket = await self._connect_websocket_with_retry(
                "prosody", {"prosody": {}}
            )
            
            self.language_websocket = await self._connect_websocket_with_retry(
                "language", {"language": {"granularity": "passage"}}
            )
            
            self.face_websocket = await self._connect_websocket_with_retry(
                "face", {"face": {}}
            )
            
            # Set running flag and start processing tasks
            self.running = True
            self.process_task = asyncio.create_task(self._process_task())
            self.process_video_task = asyncio.create_task(self._process_task_video())
            
            logger.info("Successfully connected to all Hume WebSockets and started processing tasks")
            
        except Exception as e:
            logger.error(f"Failed to start Hume connections: {e}")
            await self.stop_hume()  # Clean up any connections that might have been established
        logger.info("Started Hume WebSocket processors")

    async def on_push_frame(self, data: FramePushed):
        frame = data.frame
        if frame.id in self._frames_seen:
            return
        self._frames_seen.add(frame.id)
        if isinstance(frame, StartFrame):
            logger.info("Starting Hume WebSocket connection")
            await self.start_hume(frame)
        elif isinstance(frame, BotStartedSpeakingFrame):
            logger.info("Bot started speaking")
            self.bot_is_speaking = True
            await self._call_event_handler("on_bot_started_speaking")
        elif isinstance(frame, BotStoppedSpeakingFrame):
            logger.info("Bot stopped speaking")
            self.bot_is_speaking = False
            await self._call_event_handler("on_bot_stopped_speaking")
        elif isinstance(frame, UserStartedSpeakingFrame):
            logger.info("User started speaking")
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
        elif isinstance(frame, ImageRawFrame):
            #logger.info(f"Image frame received: {frame}")
            # Add image frame to the queue for processing by the websocket thread
            # We queue the whole frame to retain any metadata (format, size) that might be present
            # Also record the timestamp when the frame was detected
            timestamp = datetime.now(timezone.utc).isoformat()
            await self.image_queue.put(ImageFrameWithTimestamp(frame=frame, timestamp=timestamp))
            self.process_video = True
           
        #if (not self.bot_is_speaking) and self.process_frames and isinstance(frame, InputAudioRawFrame) and data.direction == FrameDirection.DOWNSTREAM:
            #logger.info(f"Processing frame: {frame} direction: {data.direction}")
            # Instead of sending immediately, add to buffer
        #    async with self.buffer_lock:
        #        self.audio_buffer.append(frame.audio)
        #        self.buffer_event.set()  # Signal that data is available
            
        if isinstance(frame, (CancelFrame, EndFrame)):
            logger.info("Stopping Hume WebSocket connection")
            await self.stop_hume()

    async def _process_task_video(self):
        """Process image frames sent to Hume's face emotion API."""
        while self.running:
            try:
                # Use a timeout to prevent indefinite blocking
                try:
                    # Wait up to 0.5 seconds for image frame with timestamp
                    frame_with_timestamp = await asyncio.wait_for(self.image_queue.get(), timeout=0.5)
                    
                    # Only process if we're supposed to be processing video frames
                    if self.process_video:
                        # Extract the actual frame and timestamp
                        image_frame = frame_with_timestamp.frame
                        timestamp = frame_with_timestamp.timestamp
                        
                        # Get the raw image data from the frame
                        image_data = image_frame.image
                        #logger.info(f"Processing image frame, size: {len(image_data)} bytes")
                        
                        # We need to convert it to JPEG before sending
                        try:
                            # Create a buffer for the JPEG image
                            buffer = io.BytesIO()
                            
                            # Get image format and size from the frame if available
                            # Extract format and size from ImageRawFrame attributes
                            format = getattr(image_frame, 'format', 'RGB')
                            
                            # Extract width and height from the size tuple
                            if hasattr(image_frame, 'size') and isinstance(image_frame.size, tuple) and len(image_frame.size) == 2:
                                width, height = image_frame.size
                            else:
                                # Fallback to default dimensions if size attribute is unavailable or invalid
                                width, height = 640, 480
                            
                            # Convert the raw bytes to a PIL Image and save as JPEG
                            Image.frombytes(format, (width, height), image_data).save(buffer, format="JPEG")
                            
                            # Get the JPEG data and encode as base64
                            buffer.seek(0)
                            jpeg_data = buffer.getvalue()
                            image_b64 = base64.b64encode(jpeg_data).decode('utf-8')
                            #logger.info(f"Converted image to JPEG, new size: {len(jpeg_data)} bytes")
                            
                            # Create the request message for the face model
                            message = {
                                "data": image_b64,
                                "models": {"face": {}}
                            }
                            
                            # Send the message to Hume API using the face websocket
                            try:
                                await self.face_websocket.send(json.dumps(message))
                                response = await self.face_websocket.recv()
                                face_data = json.loads(response)
                                
                                # Check for error
                                if face_data.get('error'):
                                    logger.warning(f"Error from Hume face model: {face_data.get('error')}")
                                else:
                                    # Process face emotion data
                                    face_predictions = face_data.get('face', {}).get('predictions', [])
                                    if face_predictions:
                                        #logger.info(f"Face emotions detected: {len(face_predictions)} faces")
                                        # Trigger event with face emotion data
                                        await self._call_event_handler("on_face_emotions_received", {"face": face_data.get('face', {})})
                                        
                                        # Send facial data to local server
                                        await self._send_facial_data_to_server(face_predictions, timestamp)
                                    else:
                                        logger.info("No faces detected in the image")
                            except (websockets.exceptions.ConnectionClosed, ConnectionError) as e:
                                logger.warning(f"Face WebSocket connection lost: {e}. Attempting to reconnect...")
                                reconnected = await self._reconnect_websocket('face_websocket', 'face', {"face": {}})
                                if not reconnected:
                                    logger.error("Failed to reconnect to face WebSocket. Will retry on next frame.")
                        
                        except Exception as e:
                            logger.error(f"Error converting image to JPEG: {e}")
                            # Skip processing this frame if we can't convert it
                            self.image_queue.task_done()
                            continue
                    
                    # Mark the task as done
                    self.image_queue.task_done()
                    
                except asyncio.TimeoutError:
                    # No image data available within timeout, continue to next iteration
                    pass
                    
            except websockets.ConnectionClosed:
                logger.error("Hume face WebSocket connection closed.")
                break
            except Exception as e:
                logger.error(f"Error in hume face process task: {e}")
                # Don't break the loop on error, just continue
        
        logger.info("Video process task stopped")

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
                        while self.audio_buffer and (collected_size < self.buffer_threshold_bytes):
                            chunk = self.audio_buffer.popleft()
                            audio_data.extend(chunk)
                            collected_size += len(chunk)
                        # Reset event if buffer is empty
                        if not self.audio_buffer:
                            logger.info("Audio buffer emptied")
                            self.buffer_event.clear()

                    # Send collected audio to Hume
                    logger.info(f"Sending audio to Hume : {collected_size} bytes, audio_buffer size: {len(self.audio_buffer)}")
                    if audio_data:

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
                        try:
                            await self.prosody_websocket.send(json.dumps(message))
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
                                # Trigger event with accumulated emotion data
                                await self._call_event_handler("on_emotions_received", {"prosody": prosody_data})    
                             

                        except (websockets.exceptions.ConnectionClosed, ConnectionError) as e:
                            logger.warning(f"Prosody WebSocket connection lost: {e}. Attempting to reconnect...")
                            reconnected = await self._reconnect_websocket('prosody_websocket', 'prosody', {"prosody": {}})
                            if not reconnected:
                                logger.error("Failed to reconnect to prosody WebSocket. Will retry on next data.")
                    
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

    async def _process_text(self, text, timestamp=None):
        """Process transcription text with Hume language model.
        
        Args:
            text: The text to process
            timestamp: ISO format timestamp when the text was captured (optional)
        """
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
            try:
                await self.language_websocket.send(json.dumps(message))
                response = await self.language_websocket.recv()
                language_data = json.loads(response)
                #logger.info(f"Language data received: {language_data}")
                
                # Check for error
                if language_data.get('error'):
                    logger.warning(f"Error from Hume language model: {language_data.get('error')}")
                    return
                    
                # Process language emotions from received data
                language_predictions = language_data.get('language', {}).get('predictions', [])
                
                # Prepare language emotions data with all available information
                language_emotions_data = {
                    'language': language_data.get('language', {})
                }
                
                # Add timestamp if provided
                if timestamp:
                    language_emotions_data['timestamp'] = timestamp
            
                # Trigger event with language emotion data
                await self._call_event_handler("on_language_emotions_received", language_emotions_data)
                
            except (websockets.exceptions.ConnectionClosed, ConnectionError) as e:
                logger.warning(f"Language WebSocket connection lost: {e}. Attempting to reconnect...")
                reconnected = await self._reconnect_websocket('language_websocket', 'language', {"language": {"granularity": "passage"}})
                if not reconnected:
                    logger.error("Failed to reconnect to language WebSocket. Will retry on next text.")
            
        except Exception as e:
            logger.error(f"Error processing text with Hume language model: {e}")
    
    async def _get_current_session_id(self):
        """Query the current session ID from the facial data server.
        
        Returns:
            int: The current session ID
        """
        try:
            # Check if we need to refresh the session ID
            current_time = time.time()
            if (self.facial_data_session_id is None or 
                current_time - self.last_session_id_query_time > self.session_id_refresh_interval):
                
                async with aiohttp.ClientSession() as session:
                    async with session.get("http://localhost:8089/session") as response:
                        if response.status == 200:
                            data = await response.json()
                            if 'session_id' in data:
                                self.facial_data_session_id = data['session_id']
                                self.last_session_id_query_time = current_time
                                logger.debug(f"Updated session ID to: {self.facial_data_session_id}")
                        else:
                            logger.warning(f"Failed to get current session ID: HTTP {response.status}")
                            self.facial_data_session_id = 0
            

            return self.facial_data_session_id
                
        except Exception as e:
            logger.error(f"Error getting current session ID: {e}")
            # Return default if unable to get from server
            return 0
    
    async def _send_facial_data_to_server(self, face_predictions, timestamp):
        """Send facial emotion data to the local server.
        
        Args:
            face_predictions: List of face prediction data from Hume API
            timestamp: ISO format timestamp string when the frame was captured
        """
        try:
            # Increment frame counter
            self.facial_frame_counter += 1
            
            # Process only the first face prediction for now (most prominent face)
            if face_predictions and len(face_predictions) > 0:
                prediction = face_predictions[0]
                
                # Extract face data
                face_id = prediction.get('face_id', f'face_{self.facial_frame_counter}')
                prob = prediction.get('prob', 0.0)
                bbox = prediction.get('bbox', {})
                
                # Extract emotions
                emotions = {}
                if 'emotions' in prediction:
                    # Map emotions from Hume format to our server format
                    for emotion in prediction['emotions']:
                        name = emotion.get('name')
                        score = emotion.get('score')
                        if name and score is not None:
                            emotions[name] = score
                
                # Get current session ID from server
                session_id = await self._get_current_session_id()
                if not session_id:
                    logger.warning("No session ID available, skipping facial data send")
                    return
                
                # Prepare payload for the server
                payload = {
                    "session_id": session_id,
                    "timestamp": timestamp,
                    "frame": self.facial_frame_counter,
                    "prob": prob,
                    "bbox": bbox if bbox else {"x": 0, "y": 0, "width": 0, "height": 0},
                    "face_id": face_id,
                    "emotions": emotions
                }
                
                # Send to local server
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        "http://localhost:8089/facial-data",
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    ) as response:
                        if response.status == 200:
                            logger.debug(f"Facial data successfully sent to server")
                        else:
                            logger.warning(f"Failed to send facial data: HTTP {response.status}")
            
        except Exception as e:
            logger.error(f"Error sending facial data to server: {e}")
    
    async def stop_hume(self):
        """Clean up resources."""
        self.running = False
        if self.process_task:
            self.process_task.cancel()
            try:
                await self.process_task
            except asyncio.CancelledError:
                pass
                
        if self.process_video_task:
            self.process_video_task.cancel()
            try:
                await self.process_video_task
            except asyncio.CancelledError:
                pass
        
        # Close all websocket connections
        if self.prosody_websocket:
            await self.prosody_websocket.close()
            
        if self.language_websocket:
            await self.language_websocket.close()
            
        if self.face_websocket:
            await self.face_websocket.close()
            
        # Clear text queue
        while not self.text_queue.empty():
            try:
                self.text_queue.get_nowait()
                self.text_queue.task_done()
            except asyncio.QueueEmpty:
                break
                
        # Clear image queue
        while not self.image_queue.empty():
            try:
                self.image_queue.get_nowait()
                self.image_queue.task_done()
            except asyncio.QueueEmpty:
                break

        # Clear buffer
        async with self.buffer_lock:
            self.audio_buffer.clear()
            self.buffer_event.clear()
