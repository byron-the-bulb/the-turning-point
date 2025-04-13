#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import argparse
import asyncio
import os
import sys
import argparse

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.cartesia.tts import CartesiaTTSService, Language
from pipecat.services.elevenlabs import ElevenLabsTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.services.daily import DailyTransport, DailyParams
from pipecat.services.whisper import WhisperSTTService, Model
from pipecat.processors.frameworks.rtvi import RTVIProcessor, RTVIConfig, RTVIObserver, RTVIMessage, RTVIAction, RTVIActionArgument
from pipecat_flows import FlowManager
from sphinx_script import sphinx_flow_config
from status_utils import status_updater
from custom_flow_manager import CustomFlowManager
from pipecat.processors.frame_processor import FrameDirection
from pipecat.frames.frames import TextFrame, BotStoppedSpeakingFrame, TranscriptionFrame
from uuid import uuid4
from pipecat.utils.time import time_now_iso8601
import json
import base64


load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


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
                "I'm sorry, we are ending the call now. Please feel free to reach out again if you need assistance."
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


class CustomRTVIProcessor(RTVIProcessor):
    def __init__(self, config):
        super().__init__(config=config)
        self.flow_manager = None  # Access node config (task messages)
        self.speech_count = 0            # Track TextFrames sent to TTS
        self.is_final = False

    def set_flow_manager(self, flow_manager):
        self.flow_manager = flow_manager

    async def process_frame(self, frame, direction):
        # Handle outbound frames (server-to-client)
        #logger.info(f"Processing frame: {frame} direction: {direction}")

        if direction == FrameDirection.UPSTREAM:
            if isinstance(frame, BotStoppedSpeakingFrame) and self.flow_manager:
                # Check if this is the final speech segment
                logger.info(f"BotStoppedSpeakingFrame received: {self.speech_count}")
                # Get current node configuration properly
                if self.flow_manager.current_node and self.flow_manager.current_node in self.flow_manager.nodes:
                    self.speech_count += 1
                    current_node_config = self.flow_manager.nodes[self.flow_manager.current_node]
                    total_messages = len(current_node_config.get("task_messages", []))
                    if self.speech_count == total_messages:
                        logger.info(f"Final speech segment received: {self.speech_count}")
                        await status_updater.trigger_ui_override()                  # Send a message to the client to display ui_override
                        self.speech_count = 0
                        self.is_final = False

        # Existing logic for inbound frames (client-to-server)
        #if direction == FrameDirection.DOWNSTREAM and hasattr(frame, 'label') and frame.label == "rtvi-ai":
        #    if frame.type == "sphinx_text_input":  # For button clicks
        #        text = frame.data.get("text", "")
        #        if text:
        #            await self.queue_frame(TextFrame(text))
        #    elif frame.type == "sphinx_list_selection":  # For dropdown selections
        #        selection = frame.data.get("selection", "")
        #       if selection:
        #            await self.queue_frame(TextFrame(selection))

        # Pass the frame to the parent class for default processing
        return await super().process_frame(frame, direction)




async def run_bot(room_url, token, identifier, data=None):
    """Run the Sphinx voice bot with the provided room URL and token.
    
    Args:
        room_url: The URL of the Daily room to connect to
        token: The access token for the Daily room
        identifier: A unique identifier for this bot instance
        data: Optional JSON-encoded data passed from the server
    """
    logger.info(f"Starting Sphinx bot in room {room_url} with identifier {identifier}")
    
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
    
    transport = DailyTransport(
        room_url=room_url,
        token=token,
        bot_name="Sphinx",
        params=DailyParams(
            audio_out_enabled=True,
            add_wav_header=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
            session_timeout=60 * 2,
        ),
    )
    
    llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o")
    
    stt = WhisperSTTService(
            api_key=os.getenv("OPENAI_API_KEY"),
            model=Model.DISTIL_MEDIUM_EN
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
            "content": "You are Sphinx, a helpful and friendly voice assistant. Keep your responses concise and conversational.",
        },
    ]

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)
    
    rtvi = CustomRTVIProcessor(config=RTVIConfig(config=[]))
    await status_updater.initialize(rtvi, identifier, room_url)
    pipeline = Pipeline(
        [
            transport.input(),  # Websocket input from client
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
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=16000,
            audio_out_sample_rate=16000,
            allow_interruptions=True,
        ),
        observers=[RTVIObserver(rtvi)]
    )

    flow_manager = CustomFlowManager(
        task=task,
        llm=llm,
        context_aggregator=context_aggregator, 
        tts=tts,
        flow_config=sphinx_flow_config
    )

    rtvi.set_flow_manager(flow_manager)

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

    @transport.event_handler("on_participant_joined")
    async def on_participant_joined(transport, participant):
        # Kick off the conversation.
        participant_id = participant['id']
        logger.info(f"New client connected: {participant_id} using identifier {identifier}")
        
        try:
            # Update status updater with the participant ID
            await status_updater.initialize(rtvi, identifier, room_url)
            logger.info(f"StatusUpdater initialized with identifier: {identifier}")
            
            # Start transcription for the user
            await transport.capture_participant_transcription(participant_id)
            
            # Initialize the flow manager
            await flow_manager.initialize()
        except Exception as e:
            logger.error(f"Error during client connection handling: {e}")

    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport, participant, reason):
        # Close the status updater session
        await status_updater.close()
        
        # Cancel the pipeline, which stops processing and removes the bot from the room
        await task.cancel()

    runner = PipelineRunner()
    await runner.run(task)


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