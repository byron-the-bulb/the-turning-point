#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import asyncio
import os
import sys

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import (
    BotInterruptionFrame, DataFrame, EndFrame, TextFrame, TranscriptionFrame,
    TransportMessageFrame
)
from dataclasses import dataclass
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.serializers.protobuf import ProtobufFrameSerializer
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.network.websocket_server import (
    WebsocketServerParams,
    WebsocketServerTransport,
)
from pipecat.services.whisper import WhisperSTTService, Model
from pipecat_flows import FlowManager
from sphinx_script import sphinx_flow_config



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



class CustomVADAnalyzer(SileroVADAnalyzer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transport = None
        self.speaking = False

    def set_transport(self, transport):
        self.transport = transport
        transport._register_event_handler("on_user_speaking_started")
        transport._register_event_handler("on_user_speaking_stopped")

    async def analyze(self, frame):
        result = await super().analyze(frame)
        if self.transport:
            if result and not self.speaking:
                self.speaking = True
                await self.transport.emit("on_user_speaking_started")
            elif not result and self.speaking:
                self.speaking = False
                await self.transport.emit("on_user_speaking_stopped")
        return result

async def main():
    # Create the custom VAD analyzer
    vad_analyzer = CustomVADAnalyzer()
    serializer = ProtobufFrameSerializer()

    transport = WebsocketServerTransport(
        params=WebsocketServerParams(
            serializer=serializer,  
            audio_out_enabled=True,
            add_wav_header=True,
            vad_enabled=True,
            vad_analyzer=vad_analyzer,
            vad_audio_passthrough=True,
            session_timeout=60 * 3,  # 3 minutes
        )
    )
    
    # Set the transport on the VAD analyzer
    vad_analyzer.set_transport(transport)

    llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o")
    messages = []
    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

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

   
    pipeline = Pipeline(
        [
            transport.input(),  # Websocket input from client
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
    )

    flow_manager = FlowManager(
        task=task,
        llm=llm,
        context_aggregator=context_aggregator, 
        tts=tts,
        flow_config=sphinx_flow_config
    )


    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        # Kick off the conversation.
        logger.info(f"New client connected: {client.remote_address}")
        
        try:
            # Send a welcome message directly via WebSocket to bypass TTS
            welcome_message = "Connected to Sphinx Voice Bot. Please start speaking when ready."
            welcome_frame = TextFrame(text=welcome_message)
            
            #Serialize and send directly to this client
            serialized_frame = await serializer.serialize(welcome_frame)
            await client.send_bytes(serialized_frame)
            #await send_status_message(welcome_message)
            logger.debug("Sent welcome message to client")
            
            # Initialize the flow manager
            await flow_manager.initialize()
        except Exception as e:
            logger.error(f"Error during client connection handling: {e}")

    @transport.event_handler("on_session_timeout")
    async def on_session_timeout(transport, client):
        logger.info(f"Entering in timeout for {client.remote_address}")

        try:
            # Send a timeout message directly via WebSocket to bypass TTS
            timeout_message = "Your session is timing out due to inactivity."
            timeout_frame = TextFrame(text=timeout_message)
            
            # Serialize and send directly to this client
            serialized_frame = await serializer.serialize(timeout_frame)
            await client.send_bytes(serialized_frame)
            
            # Then handle the timeout with the handler
            timeout_handler = SessionTimeoutHandler(task, tts)
            await timeout_handler.handle_timeout(client)
        except Exception as e:
            logger.error(f"Error during session timeout handling: {e}")

    # Add event handlers for transcription and speaking events
    # Add a function to send text frames directly to clients via WebSocket
    # This bypasses the pipeline so the messages aren't processed by TTS
    async def send_status_message(message_text):
        try:
            # Create a TextFrame that will be properly serialized
            text_frame = TextFrame(text=message_text)
            
            # Send directly through the WebSocket to bypass the TTS engine
            # This follows the Pipecat AI chatbot's recommendation
            serialized_frame = await serializer.serialize(text_frame)
            
            # Send to all connected clients
            for client in transport.clients:
                await transport.send_bytes(client, serialized_frame)
                
            logger.debug(f"Sent status message directly via WebSocket: {message_text}")
        except Exception as e:
            logger.error(f"Error sending message frame: {e}")
    
    # TranscriptionHandler defined above    
    
    @transport.event_handler("on_user_speaking_started")
    async def on_user_speaking_started(transport, client):
        logger.info(f"User at {client.remote_address} started speaking")
        
        # Notify about speech detection
        await send_status_message("[STATUS] Speech detected")
    
    @transport.event_handler("on_user_speaking_stopped")
    async def on_user_speaking_stopped(transport, client):
        logger.info(f"User at {client.remote_address} stopped speaking")
        
        # Notify that we're processing
        await send_status_message("[STATUS] Processing speech...")
    
    runner = PipelineRunner()

    await runner.run(task)


if __name__ == "__main__":
    asyncio.run(main())