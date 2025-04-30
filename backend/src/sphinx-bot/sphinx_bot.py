#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import sys
import os
from loguru import logger
from dotenv import load_dotenv

# Load environment variables first
load_dotenv(override=True)

# Remove default logger
logger.remove(0)

# Add console logging
logger.add(sys.stderr, level="DEBUG")

# Import our custom CloudWatch logger and set it up
from cloudwatch_logger import setup_cloudwatch_logging

# Setup CloudWatch logging using our separate module
setup_cloudwatch_logging()

# Now import everything else
import argparse
import asyncio
from huggingface_hub import snapshot_download

from pipecat.audio.vad.silero import SileroVADAnalyzer, VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.parallel_pipeline import ParallelPipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.cartesia.tts import CartesiaTTSService, Language
from pipecat.services.elevenlabs import ElevenLabsTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.services.daily import DailyTransport, DailyParams
from pipecat.services.whisper.stt import WhisperSTTService, Model
from pipecat.processors.frameworks.rtvi import RTVIProcessor, RTVIConfig, RTVIObserver, RTVIMessage, RTVIAction, RTVIActionArgument,RTVIServerMessageFrame
from pipecat_flows import FlowManager
from sphinx_script_dynamic import create_identify_empowered_state_node, create_initial_node
from status_utils import status_updater
from custom_flow_manager import CustomFlowManager
from pipecat.processors.frame_processor import FrameDirection
from pipecat.frames.frames import TextFrame, BotStoppedSpeakingFrame, TranscriptionFrame
from uuid import uuid4
from pipecat.utils.time import time_now_iso8601
import json
import base64
from pipecat.transports.services.helpers.daily_rest import DailyRESTHelper, DailyRoomParams
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from hume_offline_observer import HumeOfflineWebSocketObserver
from pipecat.processors.filters.stt_mute_filter import STTMuteFilter, STTMuteConfig, STTMuteStrategy


class SessionTimeoutHandler:
    """Handles actions to be performed when a session times out.
    Inputs:
    - task: Pipeline task (used to queue frames).
    - tts: TTS service (used to generate speech output).
    """

    def __init__(self, task, tts):
        self.task = task
        self.tts = tts
        self.background_tasks = set()

    async def handle_timeout(self, client_address):
        """Handles the timeout event for a session."""
        try:
            logger.info(f"Connection timeout for {client_address}")

            # Queue a BotInterruptionFrame to notify the user
            await self.task.queue_frames([BotInterruptionFrame()])

            # Send the TTS message to inform the user about the timeout
            await self.tts.say(
                "I'm sorry, we are ending the session now due to timeout."
            )

            # Start the process to gracefully end the call in the background
            end_call_task = asyncio.create_task(self._end_call())
            self.background_tasks.add(end_call_task)
            end_call_task.add_done_callback(self.background_tasks.discard)
        except Exception as e:
            logger.error(f"Error during session timeout handling: {e}")

    async def _end_call(self):
        """Completes the session termination process after the TTS message."""
        try:
            # Wait for a duration to ensure TTS has completed
            await asyncio.sleep(15)

            # Queue both BotInterruptionFrame and EndFrame to conclude the session
            await self.task.queue_frames([BotInterruptionFrame(), EndFrame()])

            logger.info("TTS completed and EndFrame pushed successfully.")
        except Exception as e:
            logger.error(f"Error during call termination: {e}")


async def run_bot(room_url, token, identifier, data=None):
    """Run the Sphinx voice bot with the provided room URL and token.
    
    Args:
        room_url: The URL of the Daily room to join.
        token: The token to use for authentication with Daily.
        identifier: Unique identifier for this bot instance.
        data: Optional JSON-encoded data passed from the server.
    """
    logger.info(f"Starting Sphinx bot with room URL: {room_url}, token: {token[:8]}..., identifier: {identifier}")
    
    # Default station name
    station_name = "Unknown Station"
    
    # Extract station name from data if available
    if data:
        try:
            # If data is a string, try to decode it
            if isinstance(data, str):
                import base64
                import json
                try:
                    # Try to decode from base64 if it's encoded that way
                    decoded_data = base64.b64decode(data).decode('utf-8')
                    data_json = json.loads(decoded_data)
                except:
                    # If not base64 encoded, try direct JSON parsing
                    data_json = json.loads(data)
                
                if 'stationName' in data_json:
                    station_name = data_json['stationName']
                    logger.info(f"Station name set to: {station_name}")
            # If data is already a dictionary
            elif isinstance(data, dict) and 'stationName' in data:
                station_name = data['stationName']
                logger.info(f"Station name set to: {station_name}")
        except Exception as e:
            logger.error(f"Error extracting station name from data: {e}")
    
    transport = DailyTransport(
        room_url=room_url,
        token=token,
        bot_name="Sphinx",
        params=DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(
                threshold=0.3,              # Sensitive to short bursts
                min_speech_duration_ms=100, # Captures brief utterances
                min_silence_duration_ms=50, # Quick response to speech end
                stop_secs=1.8,              # Tolerant of pauses in long speech
                max_speech_duration_secs=30 # Allow long utterances                
                )),
            vad_audio_passthrough=True,
            session_timeout=60 * 2,
        ),
    )
    
    llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4.1")
    
    # Get device from environment variable, default to cuda
    sphinx_whisper_device = os.getenv("SPHINX_WHISPER_DEVICE", "cuda")
    logger.info(f"Using device for Whisper STT (SPHINX_WHISPER_DEVICE): {sphinx_whisper_device}")
    
    # Check if mount point is provided and valid
    mount_point = os.getenv("SPHINX_MOUNT_POINT", None)
    repo_id = os.getenv("SPHINX_REPO_ID", None)
    model_path = None
    
    if mount_point and repo_id:
        # Format the full model path
        model_path = os.path.join(mount_point, "models", "whisper-medium-ct2")
        logger.info(f"Using mount point for Whisper model: {mount_point}")
        logger.info(f"Hugging Face repo ID: {repo_id}")
        logger.info(f"Full model path: {model_path}")
        
        # Check if model directory exists
        if not os.path.exists(model_path):
            #log the content of the network volume for debugging starting from the root of the volume
            logger.info(f"Content of the network volume: {os.listdir(mount_point)}")
            logger.info(f"Model not found at {model_path}, downloading from Hugging Face repo: {repo_id}")
            try:
                # Create the models directory if it doesn't exist
                os.makedirs(os.path.dirname(model_path), exist_ok=True)
                
                # Download the model from Hugging Face
                logger.info(f"Starting model download from Hugging Face...")
                snapshot_download(
                    repo_id=repo_id,
                    local_dir=model_path,
                    local_dir_use_symlinks=False
                )
                
                logger.info(f"Successfully downloaded model to {model_path}")
            except Exception as e:
                logger.error(f"Error downloading model from Hugging Face: {e}")
                model_path = None
        else:
            logger.info(f"Model found at {model_path}")
    
    # Initialize WhisperSTTService with model path if available
    if model_path and os.path.exists(model_path):
        logger.info(f"Using local model from {model_path}")
        stt = WhisperSTTService(
            api_key=os.getenv("OPENAI_API_KEY"),
            device=sphinx_whisper_device,
            model=model_path  # Pass the model path directly to the model parameter
        )
    else:
        logger.info("Using default Whisper model configuration")
        stt = WhisperSTTService(
            api_key=os.getenv("OPENAI_API_KEY"),
            device=sphinx_whisper_device,
            model=Model.DISTIL_MEDIUM_EN,
            no_speech_prob=0.2,
            buffer_size_secs=0.5
        )

    # Set a default TTS if not configured through data
    tts = None
    if data and isinstance(data, dict) and 'tts' in data:
        if data['tts']['provider'] == "cartesia":
            tts = CartesiaTTSService(
                api_key=os.getenv("CARTESIA_API_KEY"),
                voice_id=data['tts']['voiceId'],  
                model=data['tts']['model'],
                params=CartesiaTTSService.InputParams(
                    language=Language.EN,
                    speed=data['tts']['speed'],
                    emotion=data['tts']['emotion']
                )
            )
        elif data['tts']['provider'] == "elevenlabs":
            tts = ElevenLabsTTSService(
                api_key=os.getenv("ELEVENLABS_API_KEY"),
                voice_id=data['tts']['voiceId'], 
                params=ElevenLabsTTSService.InputParams(
                    stability=data['tts']['stability'],
                    similarity_boost=data['tts']['similarity_boost'],
                    style=data['tts']['style'],
                    user_speaker_boost=data['tts']['user_speaker_boost']
                ) 
            )
    
    # Ensure TTS is not None by setting a default if needed
    if tts is None:
        logger.info("No TTS configuration found, using default CartesiaTTSService")
        tts = CartesiaTTSService(
            api_key=os.getenv("CARTESIA_API_KEY"),
            voice_id="ec58877e-44ae-4581-9078-a04225d42bd4", # Default voice
            model="sonic-2-2025-03-07",
            params=CartesiaTTSService.InputParams(
                language=Language.EN,
                speed="slow",
                emotion=None
            )
        )

    messages = [
        {
            "role": "system",
            "content": "You are Sphinx, a wise, helpful and friendly voice assistant. Keep your responses concise and conversational. Speak slowly and calmly. Always call the provided functions, never skip.",
        },
    ]

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    stt_mute_filter = STTMuteFilter(
        config=STTMuteConfig(strategies={
            STTMuteStrategy.ALWAYS
        })
    )

    rtvi = RTVIProcessor(config=RTVIConfig(config=[]))
    await status_updater.initialize(rtvi, identifier, room_url, station_name)
    hume_observer = HumeOfflineWebSocketObserver(api_key=os.getenv("HUME_API_KEY"), rtvi=rtvi)
    conversation_pipeline = Pipeline(
        [
            transport.input(),  # Websocket input from client
            rtvi,
            stt_mute_filter,
            stt,  # Speech-To-Text
            context_aggregator.user(),
            llm,  # LLM
            tts,  # Text-To-Speech
            transport.output(),  # Websocket output to client
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        conversation_pipeline,
        params=PipelineParams(
            audio_in_sample_rate=16000,
            audio_out_sample_rate=48000,
            allow_interruptions=True,
        ),
        observers=[RTVIObserver(rtvi), hume_observer]
    )

    flow_manager = CustomFlowManager(
        task=task,
        llm=llm,
        context_aggregator=context_aggregator, 
        tts=tts
    )

    #rtvi.set_flow_manager(flow_manager)

    async def handle_uioverride_response(processor, service, arguments):
        """Handler for UI override response action"""
        message = arguments.get("message", "Default message")
        logger.info(f"UI override response triggered with message: {message}")
        await processor.queue_frame(TranscriptionFrame(message, "", time_now_iso8601()), direction=FrameDirection.DOWNSTREAM)
        return True

    uioverride_response_action = RTVIAction(
        service="conversation",
        action="uioverride_response",
        arguments=[
            RTVIActionArgument(name="message", type="string")
        ],
        result="bool",
        handler=handle_uioverride_response
    )

    rtvi.register_action(uioverride_response_action)

    @hume_observer.event_handler("on_start_processing_emotions")
    async def on_start_processing_emotions(hume_processor):
        logger.info("Starting to process emotions")
        # Reset accumulated emotions
        flow_manager.state["emotions_summary"] = ""
        flow_manager.state["emotions_fully_processed"] = False
        # Initialize emotion storage for prosody and language
        flow_manager.state["prosody_emotions"] = None
        flow_manager.state["language_emotions"] = None

    # Helper function to combine emotions and generate a summary
    async def process_combined_emotions():
        try:
            prosody_emotions = flow_manager.state.get("prosody_emotions")
            language_emotions = flow_manager.state.get("language_emotions")
            
            # If we don't have both sets of emotions yet, we can't proceed
            if not prosody_emotions or not language_emotions:
                logger.info("Still waiting for both prosody and language emotions")
                return
            
            logger.info("Both prosody and language emotions received, generating combined summary")
            
            # Create dictionaries from both emotion lists for easier matching
            prosody_dict = {emotion.get("name"): emotion.get("score", 0) for emotion in prosody_emotions}
            language_dict = {emotion.get("name"): emotion.get("score", 0) for emotion in language_emotions}
            
            # Multiply matching emotions together
            combined_emotions = {}
            for emotion_name in set(prosody_dict.keys()).union(language_dict.keys()):
                prosody_score = prosody_dict.get(emotion_name, 0)
                language_score = language_dict.get(emotion_name, 0)
                
                # If both scores exist, multiply them; otherwise use a weighted combination
                if prosody_score > 0 and language_score > 0:
                    # Multiply scores and scale to keep in reasonable range
                    combined_score = (prosody_score * language_score) ** 0.5  # Square root to normalize scale
                else:
                    # If only one score exists, use it at 70% strength
                    combined_score = max(prosody_score, language_score) * 0.7
                
                combined_emotions[emotion_name] = combined_score
            
            flow_manager.state["combined_emotions"] = combined_emotions
            # Sort emotions by combined score and take top 3
            top_emotions = sorted(combined_emotions.items(), key=lambda x: x[1], reverse=True)[:3]
            
            # Create a readable summary
            if len(top_emotions) >= 3:
                summary = f"{top_emotions[0][0]}, {top_emotions[1][0]} and {top_emotions[2][0]}"
            elif len(top_emotions) == 2:
                summary = f"{top_emotions[0][0]} and {top_emotions[1][0]}"
            elif len(top_emotions) == 1:
                summary = top_emotions[0][0]
            else:
                summary = "No significant emotions detected"
            
            logger.info(f"Combined emotion summary: {summary}")
            flow_manager.state["emotions_summary"] = summary
            
            # Mark emotions as fully processed
            flow_manager.state["emotions_fully_processed"] = True
            
        except Exception as e:
            logger.error(f"Error processing combined emotions: {e}")

    @hume_observer.event_handler("on_emotions_received")
    async def on_emotions_received(hume_observer, prosody_data):
        logger.info(f"Prosody emotions received")
        try:
            # Send emotions to client for displaying
            message = {
                "emotion": prosody_data
            }
            status_frame = RTVIServerMessageFrame(message)
            await rtvi.push_frame(status_frame)               
            
            # Store prosody emotions
            preds = prosody_data.get("prosody", {}).get("predictions", [])
            if preds and len(preds) > 0 and "emotions" in preds[0]:
                flow_manager.state["prosody_emotions"] = preds[0].get("emotions", [])
                
                # Try to process combined emotions if we have both sets
                await process_combined_emotions()
            
        except Exception as e:
            logger.error(f"Error processing prosody emotions: {e}")
    
    @hume_observer.event_handler("on_language_emotions_received")
    async def on_language_emotions_received(hume_observer, language_data):
        logger.info(f"Language emotions received")
        try:
            # Send language emotions to client for displaying
            message = {
                "language_emotion": language_data
            }
            status_frame = RTVIServerMessageFrame(message)
            await rtvi.push_frame(status_frame)
            
            # Store language emotions
            accumulated_emotions = language_data.get("language", {}).get("accumulated_emotions", [])
            if accumulated_emotions:
                flow_manager.state["language_emotions"] = accumulated_emotions
                
                # Try to process combined emotions if we have both sets
                await process_combined_emotions()
                
        except Exception as e:
            logger.error(f"Error processing language emotion data: {e}")

    @transport.event_handler("on_participant_joined")
    async def on_participant_joined(transport, participant):
        #await audiobuffer.start_recording()
        # Kick off the conversation.
        participant_id = participant['id']
        logger.info(f"New client connected: {participant_id} using identifier {identifier}")
        
        try:
            # Update status updater with the participant ID
            await status_updater.initialize(rtvi, identifier, room_url, station_name)
            logger.info(f"StatusUpdater initialized with identifier: {identifier} and station name: {station_name}")
            
            # Start transcription for the user
            await transport.capture_participant_transcription(participant_id)
            
            # Initialize the flow manager
            await flow_manager.initialize()

            # Start the flow manager
            await flow_manager.set_node("greeting", create_initial_node())
        except Exception as e:
            logger.error(f"Error during client connection handling: {e}")

    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport, participant, reason):
        logger.info(f"Participant left: {participant['id']}, reason: {reason}")
        try:           
            if room_url and os.getenv("DAILY_API_KEY"):
                import aiohttp
                # Initialize Daily REST helper with proper aiohttp session
                async with aiohttp.ClientSession() as session:
                    daily_rest = DailyRESTHelper(
                        daily_api_key=os.getenv("DAILY_API_KEY", ""),
                        daily_api_url=os.getenv("DAILY_API_URL", "https://api.daily.co/v1"),
                        aiohttp_session=session
                    )

                    logger.info(f"Deleting Daily room: {room_url}")
                    try:
                        success = await daily_rest.delete_room_by_url(room_url)
                        if success:
                            logger.info(f"Successfully deleted room: {room_url}")
                        else:
                            logger.error(f"Failed to delete room: {room_url}")
                    except Exception as e:
                        logger.error(f"Error deleting Daily room: {e}")
        except Exception as e:
            logger.error(f"Error in on_participant_left: {e}")
        finally:
            # Close the status updater session
            await status_updater.close()
            
            # Cancel the pipeline, which stops processing and removes the bot from the room
            await task.cancel()
            
            # Log that we're exiting the process
            logger.info("Participant left, canceling pipeline task...")
            
            # Give a small delay to allow logs to flush
            await asyncio.sleep(1)
            
            # Instead of sys.exit, raise an exception that will be caught by the outer try/except
            # This allows for proper cleanup of resources
            raise asyncio.CancelledError("Participant left the room")

    try:
        runner = PipelineRunner()
        await runner.run(task)
    except asyncio.CancelledError:
        logger.info("Pipeline runner cancelled, shutting down gracefully...")
    except Exception as e:
        logger.error(f"Error in pipeline runner: {e}")
        # Exit with error code
        import sys
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sphinx Voice Bot")
    parser.add_argument(
        "-u", "--url", required=True, help="Room URL to connect to"
    )
    parser.add_argument(
        "-t", "--token", required=True, help="Access token for the room"
    )

    parser.add_argument(
        "-i", "--identifier", required=True, help="Unique bot identifier"
    )

    parser.add_argument(
        "-d", "--data", help="Optional JSON-encoded data passed from the server"
    )

    args = parser.parse_args()
       
    asyncio.run(run_bot(args.url, args.token, args.identifier, args.data))