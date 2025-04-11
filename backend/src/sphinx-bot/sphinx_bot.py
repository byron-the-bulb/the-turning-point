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
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.services.daily import DailyTransport, DailyParams
from pipecat.services.whisper import WhisperSTTService, Model
from pipecat.processors.frameworks.rtvi import RTVIProcessor, RTVIConfig, RTVIObserver
from pipecat_flows import FlowManager
from sphinx_script import sphinx_flow_config
from status_utils import status_updater



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

# Using TextFrame for consistency with Pipecat
# Note: TextFrame is already part of the Pipecat framework and should be properly handled
# by both the pipeline and the serializer


async def run_bot(room_url, token, identifier):
    """Run the Sphinx voice bot with the provided room URL and token."""
    logger.info(f"Starting Sphinx bot in room {room_url} with identifier {identifier}")


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

    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id="f114a467-c40a-4db8-964d-aaba89cd08fa",  
    )

    messages = [
        {
            "role": "system",
            "content": "You are Sphinx, a helpful and friendly voice assistant. Keep your responses concise and conversational.",
        },
    ]

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)
    
    rtvi = RTVIProcessor(config=RTVIConfig(config=[]))
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

    flow_manager = FlowManager(
        task=task,
        llm=llm,
        context_aggregator=context_aggregator, 
        tts=tts,
        flow_config=sphinx_flow_config
    )

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

    args = parser.parse_args()

    asyncio.run(run_bot(args.url, args.token, args.identifier))