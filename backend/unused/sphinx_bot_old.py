import asyncio
import base64
import logging
import os
from typing import Any, AsyncGenerator, Dict

from pipecat.frames.frames import AudioRawFrame, EndFrame, Frame, LLMFullResponseEndFrame, LLMFullResponseStartFrame, TextFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.processors import Processor, FrameDirection
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.openai.llm import OpenAILLMService, OpenAILLMContextAggregator
from pipecat.services.whisper import WhisperSTTService, Model

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

class ResponseHandler(Processor):
    """Handles LLM responses and triggers TTS, yielding results to the client."""
    def __init__(self, tts_service: CartesiaTTSService):
        super().__init__()
        self.tts_service = tts_service
        self.response_text = ""
        self.queue = asyncio.Queue()  # For yielding frames to the caller

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if isinstance(frame, LLMFullResponseStartFrame):
            self.response_text = ""
        elif isinstance(frame, TextFrame) and frame.source == self.llm_service:
            self.response_text += frame.text
            await self.queue.put({"type": "response", "text": frame.text, "is_final": False})
        elif isinstance(frame, LLMFullResponseEndFrame):
            await self.queue.put({"type": "response", "text": self.response_text, "is_final": True})
            tts_frame = TTSSpeakFrame(self.response_text)
            await self.push_frame(tts_frame)
        elif isinstance(frame, AudioRawFrame):
            audio_base64 = base64.b64encode(frame.audio).decode()
            await self.queue.put({"type": "audio", "data": audio_base64, "is_final": True})
        await self.push_frame(frame)

class SphinxBot:
    """
    Sphinx Voice Bot that processes audio input, transcribes it, generates responses,
    and converts them to speech using Pipecat AI services.
    """

    def __init__(self, session_id: str):
        """
        Initialize the SphinxBot.

        Args:
            session_id: Unique identifier for the user session
        """
        self.session_id = session_id

        # Initialize Pipecat services
        self.whisper_service = WhisperSTTService(
            api_key=os.getenv("OPENAI_API_KEY"),
            model=Model.DISTIL_MEDIUM_EN
        )
        self.llm_service = OpenAILLMService(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4o",
            temperature=0.7
        )
        self.tts_service = CartesiaTTSService(
            api_key=os.getenv("CARTESIA_API_KEY"),
            voice_id="f114a467-c40a-4db8-964d-aaba89cd08fa"
        )

        # Initialize conversation history with system prompt
        self.conversation_history = [
            {"role": "system", "content": "You are Sphinx, a helpful and friendly voice assistant. Keep your responses concise and conversational."}
        ]
        self.context_aggregator = OpenAILLMContextAggregator(self.llm_service)

    async def process_audio(self, audio_data: bytes) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process audio data from the client.

        Args:
            audio_data: Raw audio bytes from the client

        Yields:
            Dict with response data for the client
        """
        try:
            # Create AudioRawFrame from input (assuming 16kHz, mono)
            audio_frame = AudioRawFrame(audio_data, sample_rate=16000, num_channels=1)

            # Create a custom processor to handle responses and TTS triggering
            response_handler = ResponseHandler(self.tts_service)
            ResponseHandler.llm_service = self.llm_service  # Hack to access llm_service in ResponseHandler

            # Define the pipeline
            pipeline = Pipeline([
                self.whisper_service,  # AudioRawFrame -> TextFrame (transcript)
                self.context_aggregator,  # Updates LLM context
                self.llm_service,  # Generates response frames
                response_handler,  # Handles LLM response and triggers TTS
                self.tts_service  # TTSSpeakFrame -> AudioRawFrame
            ])

            # Create and run the pipeline task
            task = PipelineTask(pipeline)
            await task.queue_frame(audio_frame)
            await task.queue_frame(EndFrame())

            # Start the pipeline in the background
            runner_task = asyncio.create_task(task.run())

            # Process transcript separately since it comes before the response handler
            async for frame in task.frames():
                if isinstance(frame, TextFrame) and frame.source == self.whisper_service:
                    self.conversation_history.append({"role": "user", "content": frame.text})
                    await self.context_aggregator.queue_frame(TextFrame(frame.text))  # Update context
                    yield {"type": "transcript", "text": frame.text, "is_final": True}
                    break  # Only need the first transcript frame

            # Yield responses from the response handler as they arrive
            while True:
                result = await response_handler.queue.get()
                yield result
                if result["type"] == "audio" and result["is_final"]:
                    break

            await runner_task  # Ensure the pipeline completes

        except Exception as e:
            logger.error(f"Error processing audio: {e}", exc_info=True)
            yield {"type": "error", "text": f"Error processing request: {str(e)}", "is_final": True}

    async def process_text(self, text: str) -> Dict[str, Any]:
        """
        Process text input directly (for testing or fallback).

        Args:
            text: Text message from the client

        Returns:
            Dict with response data for the client
        """
        try:
            self.conversation_history.append({"role": "user", "content": text})
            response_handler = ResponseHandler(self.tts_service)
            ResponseHandler.llm_service = self.llm_service

            pipeline = Pipeline([
                self.context_aggregator,
                self.llm_service,
                response_handler,
                self.tts_service
            ])

            task = PipelineTask(pipeline)
            await task.queue_frame(TextFrame(text))
            await task.queue_frame(EndFrame())

            runner_task = asyncio.create_task(task.run())
            final_result = {}
            while True:
                result = await response_handler.queue.get()
                if result["type"] == "response" and result["is_final"]:
                    self.conversation_history.append({"role": "assistant", "content": result["text"]})
                    final_result = result
                elif result["type"] == "audio":
                    final_result.update({"data": result["data"], "type": "audio"})
                    await runner_task
                    return final_result
        except Exception as e:
            logger.error(f"Error processing text: {e}", exc_info=True)
            return {"type": "error", "text": f"Failed to process input: {str(e)}", "is_final": True}

    async def cleanup(self):
        """Clean up resources when the bot is no longer needed."""
        # Cleanup logic can be added if services require it
        pass