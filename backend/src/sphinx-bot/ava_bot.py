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
from pipecat.services.grok.llm import GrokLLMService
from pipecat.transports.services.daily import DailyTransport, DailyParams
from pipecat.services.whisper.stt import WhisperSTTService, Model
from pipecat.processors.frameworks.rtvi import RTVIProcessor, RTVIConfig, RTVIObserver, RTVIMessage, RTVIAction, RTVIActionArgument,RTVIServerMessageFrame
from pipecat_flows import FlowManager
from muse_script_dynamic import SYSTEM_ROLE, create_initial_node
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
from hume_observer_rt import HumeObserver
from pipecat.processors.filters.stt_mute_filter import STTMuteFilter, STTMuteConfig, STTMuteStrategy
from pipecat.audio.turn.smart_turn.local_smart_turn import LocalSmartTurnAnalyzer
from pipecat.audio.turn.smart_turn.base_smart_turn import SmartTurnParams

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
        room_url: The URL of the Daily room to connect to
        token: The access token for the Daily room
        identifier: A unique identifier for this bot instance
        data: Optional JSON-encoded data passed from the server
    """
    logger.info(f"Starting Sphinx bot in room {room_url} with identifier {identifier}")
    
    # print all env variables
    #logger.info(f"All environment variables: {dict(os.environ)}")
    # Parse the data if provided
    logger.info(f"Received data: {data}")
    config_data = {}
    if data:
        try:

            # Decode base64-encoded JSON data
            decoded_data = base64.b64decode(data).decode()
            logger.info(f"Decoded data: {decoded_data}")
            config_data = json.loads(decoded_data)
            logger.info(f"Parsed configuration data: {config_data}")
        except Exception as e:
            logger.error(f"Error parsing data parameter: {e}")

    #smart_turn_model_path = os.path.join(os.getenv("SPHINX_MOUNT_POINT", "~/models"), "smart_turn_model")
    #logger.info(f"Using smart turn model path: {smart_turn_model_path}")    
    
    transport = DailyTransport(
        room_url=room_url,
        token=token,
        bot_name="Sphinx",
        params=DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(
                threshold=0.3,              # Sensitive to short bursts
                min_speech_duration_ms=100, # Captures brief utterances
                min_silence_duration_ms=50, # Quick response to speech end
                stop_secs=1.8,              # Tolerant of pauses in long speech
                max_speech_duration_secs=30 # Allow long utterances                
                )),            
            #turn_analyzer=LocalSmartTurnAnalyzer(
            #    smart_turn_model_path=None,
            #    params=SmartTurnParams(
            #        stop_secs=2.0,
            #        pre_speech_ms=0.0,
            #        max_duration_secs=8.0
            #    )
            #)
        ),
    )
    
    llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4.1")
    #llm = GrokLLMService(api_key=os.getenv("GROK_API_KEY"), model="grok-3")
    
    # Get device from environment variable, default to cuda
    sphinx_whisper_device = os.getenv("SPHINX_WHISPER_DEVICE", "cuda")
    logger.info(f"Using device for Whisper STT (SPHINX_WHISPER_DEVICE): {sphinx_whisper_device}")
    
    # Check if mount point is provided and valid
    mount_point = os.getenv("SPHINX_MOUNT_POINT", None)
    repo_id = os.getenv("SPHINX_REPO_ID", None)
    model_path = None
    
    if mount_point and repo_id:
        # Format the full model path, extract the model name from the repo ID
        model_path = os.path.join(mount_point, "models", repo_id.split('/')[-1])
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
            model=model_path,
            no_speech_prob=0.2
        )
    else:
        logger.info("Using default Whisper model configuration")
        stt = WhisperSTTService(
            api_key=os.getenv("OPENAI_API_KEY"),
            device=sphinx_whisper_device,
            model=Model.DISTIL_MEDIUM_EN,
            no_speech_prob=0.2
        )

    tts = None
    if config_data.get("tts"):
        if config_data["tts"]["provider"] == "cartesia":
            tts = CartesiaTTSService(
                api_key=os.getenv("CARTESIA_API_KEY"),
                voice_id=config_data["tts"]["voiceId"],  
                model=config_data["tts"]["model"],
                params=CartesiaTTSService.InputParams(
                    language=Language.EN,
                    speed=config_data["tts"]["speed"],
                    emotion=config_data["tts"]["emotion"]
                )
            )
        elif config_data["tts"]["provider"] == "elevenlabs":
            tts = ElevenLabsTTSService(
                api_key=os.getenv("ELEVENLABS_API_KEY"),
                voice_id=config_data["tts"]["voiceId"], 
                params=ElevenLabsTTSService.InputParams(
                    stability=config_data["tts"]["stability"],
                    similarity_boost=config_data["tts"]["similarity_boost"],
                    style=config_data["tts"]["style"],
                    user_speaker_boost=config_data["tts"]["user_speaker_boost"]
                ) 
            )

    messages = [
        {
            "role": "system",
            "content": SYSTEM_ROLE,
        },
    ]

    if config_data.get("stationName"):
        station_name = config_data["stationName"]
    else:
        station_name = "Unknown Station"

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    stt_mute_filter = STTMuteFilter(
        config=STTMuteConfig(strategies={
            STTMuteStrategy.ALWAYS
        })
    )

    rtvi = RTVIProcessor(config=RTVIConfig(config=[]))
    hume_observer = HumeObserver(api_key=os.getenv("HUME_API_KEY"))
    await status_updater.initialize(rtvi, identifier, room_url, station_name)
    conversation_pipeline = Pipeline(
        [
            transport.input(),  # Websocket input from client
            stt_mute_filter,
            rtvi,
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

    # --- Local state for bot speaking and frame caching ---
    bot_is_speaking_local = False
    cached_status_frames_local = []
    # --- End local state ---

    @hume_observer.event_handler("on_start_processing_emotions")
    async def on_start_processing_emotions_local(hume_processor):
        logger.info("Starting to process emotions (local handler)")
        # Reset accumulated emotions in flow_manager
        flow_manager.state["emotions_summary"] = ""
        flow_manager.state["emotions_fully_processed"] = False
        # Initialize emotion storage for prosody and language in flow_manager
        flow_manager.state["prosody_emotions"] = []
        flow_manager.state["language_emotions"] = []
        # Note: bot_is_speaking_local and cached_status_frames_local are handled by local vars in the run_bot scope

    @hume_observer.event_handler("on_emotions_received")
    async def on_emotions_received_local(hume_observer_param, prosody_data):
        nonlocal bot_is_speaking_local # To modify the outer scope variable
        # cached_status_frames_local is a list, can be mutated directly

        logger.info(f"Prosody emotions received (local handler)")
        try:
            # Append the emotions in the flow manager state emotions array with a timestamp
            if "prosody_emotions" not in flow_manager.state:
                flow_manager.state["prosody_emotions"] = []
            flow_manager.state["prosody_emotions"].append({"timestamp": time_now_iso8601(), "emotions": prosody_data["prosody"]})
            
            # Create status frame
            message = {
                "emotion": prosody_data
            }
            status_frame = RTVIServerMessageFrame(message)

            # If bot is speaking, cache the frame. Otherwise, send it.
            if bot_is_speaking_local:
                cached_status_frames_local.append(status_frame)
                logger.debug(f"Bot is speaking (local), caching status frame. Cache size: {len(cached_status_frames_local)}")
            else:
                await rtvi.push_frame(status_frame)
                logger.debug("Bot not speaking (local), sent status frame immediately.")
        except Exception as e:
            logger.error(f"Error processing prosody emotions (local handler): {e}")

    @hume_observer.event_handler("on_bot_started_speaking")
    async def on_bot_started_speaking_local(hume_observer_param):
        nonlocal bot_is_speaking_local
        logger.info("Bot started speaking (local handler)")
        bot_is_speaking_local = True

    @hume_observer.event_handler("on_bot_stopped_speaking")
    async def on_bot_stopped_speaking_local(hume_observer_param):
        nonlocal bot_is_speaking_local
        # cached_status_frames_local is a list, can be mutated directly

        logger.info("Bot stopped speaking (local handler)")
        bot_is_speaking_local = False
        
        if cached_status_frames_local:
            logger.info(f"Sending {len(cached_status_frames_local)} cached status frames (local cache).")
            for frame_to_send in cached_status_frames_local:
                try:
                    await rtvi.push_frame(frame_to_send)
                except Exception as e:
                    logger.error(f"Error sending cached status frame (local cache): {e}")
            cached_status_frames_local.clear()
        else:
            logger.info("No cached status frames to send (local cache).")
    
    @transport.event_handler("on_participant_joined")
    async def on_participant_joined(transport, participant):
        #await audiobuffer.start_recording()
        # Kick off the conversation.
        participant_id = participant['id']
        logger.info(f"New client connected: {participant_id} using identifier {identifier}")
        
        try:
            # Update status updater with the participant ID
            await status_updater.initialize(rtvi, identifier, room_url, station_name)
            logger.info(f"StatusUpdater initialized with identifier: {identifier}")
            
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