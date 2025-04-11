import os
import asyncio
from dotenv import load_dotenv
from loguru import logger

# Updated imports for latest Pipecat SDK
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.openai.llm import OpenAILLMService
# Use correct frame imports for Pipecat 0.0.62
from pipecat.frames.frames import TTSSpeakFrame, InputAudioRawFrame, LLMTextFrame

# Load environment variables
load_dotenv()

class VoiceProcessor:
    def __init__(self):
        self.pipeline_runner = PipelineRunner()
        
        # Configure services
        self.stt = WhisperSTTService(
            model="medium",  # Valid model name for Pipecat 0.0.62
            language="en"
        )
        
        self.llm = OpenAILLMService(
            model="gpt-4o",
            system_prompt="You are Sphinx, an AI guide for an interactive art installation. \
            Follow the script exactly, but respond naturally to the participant's inputs.\
            Analyze their emotional state based on their responses and provide insightful reflections."
        )
        
        self.tts = CartesiaTTSService(
            api_key=os.environ.get("CARTESIA_API_KEY"),
            voice_id="f114a467-c40a-4db8-964d-aaba89cd08fa"  # Your preferred voice
        )
        
    def _create_pipeline(self):
        """Create and configure the Pipecat pipeline using the latest pattern"""
        # Create pipeline with a list of processors
        pipeline = Pipeline([
            self.stt,
            self.llm,
            self.tts
        ])
        
        return pipeline
    
    async def transcribe_audio(self, audio_data):
        """Transcribe audio data to text using latest pipeline pattern"""
        # Create a pipeline task for transcription only
        pipeline = Pipeline([self.stt])
        task = PipelineTask(pipeline)
        
        # Verify we received audio data
        if not audio_data or len(audio_data) < 1000:
            print(f"WARNING: Audio data too short or empty. Size: {len(audio_data) if audio_data else 0} bytes")
            return "[Audio data too short or empty]"
            
        print(f"Processing audio data: {len(audio_data)} bytes")
        
        try:
            # Process the audio through STT
            # Use InputAudioRawFrame instead of STTFrame for Pipecat 0.0.62
            # Include required sample_rate and num_channels parameters
            await task.queue_frames([InputAudioRawFrame(
                audio_data, 
                sample_rate=16000,  # Assuming 16kHz audio
                num_channels=1      # Assuming mono audio
            )])
            
            # Set a timeout for the transcription task
            result = await asyncio.wait_for(self.pipeline_runner.run(task), 30.0)
            
            # Extract transcription from result
            transcription = result.text if result else ""
            print(f"Raw transcription result: {result}")
            
            if not transcription or transcription.strip() == "":
                print("WARNING: Empty transcription returned. Returning default message.")
                return "[No speech detected in the audio]"  # Default message
                
            return transcription
            
        except asyncio.TimeoutError:
            print("Transcription timed out. This could happen with background noise or silent audio.")
            return "[Transcription timed out]"
            
        except Exception as e:
            print(f"Error during transcription: {e}")
            return f"[Error: {str(e)}]"
    
    async def generate_response(self, text_input):
        """Generate LLM response to text input using latest pipeline pattern"""
        # Create a pipeline task for LLM only
        pipeline = Pipeline([self.llm])
        task = PipelineTask(pipeline)
        
        # Process the text through LLM
        # Use LLMTextFrame instead of LLMFrame for Pipecat 0.0.62
        await task.queue_frames([LLMTextFrame(text_input)])
        result = await self.pipeline_runner.run(task)
        
        # Extract response from result
        return result.text if result else ""
    
    async def synthesize_speech(self, text):
        """Convert text to speech using latest pipeline pattern"""
        # Check if Cartesia API key is available
        if not os.environ.get("CARTESIA_API_KEY"):
            print("WARNING: No CARTESIA_API_KEY found, returning empty audio data")
            return b''  # Return empty audio data as fallback
            
        # Create a pipeline task for TTS only
        pipeline = Pipeline([self.tts])
        task = PipelineTask(pipeline)
        await task.queue_frames([TTSSpeakFrame(text)])
        result = await self.pipeline_runner.run(task)
        
        # In Pipecat 0.0.62, the TTS service may return results in different formats
        # Extract the audio data if it exists in one of these formats
        if hasattr(result, 'audio'):
            return result.audio
        elif hasattr(result, 'audio_data'):
            return result.audio_data
        elif hasattr(result, 'buffer'):
            return result.buffer
        
        # Return the complete result if we can't extract specific audio data
        return result
    
    async def process_audio(self, audio_data):
        """Process audio through the entire pipeline using latest pattern"""
        # Create complete pipeline
        pipeline = self._create_pipeline()
        task = PipelineTask(pipeline)
        
        # Queue the audio for processing through the entire pipeline
        # Use InputAudioRawFrame instead of STTFrame for Pipecat 0.0.62
        # Include required sample_rate and num_channels parameters
        await task.queue_frames([InputAudioRawFrame(
            audio_data, 
            sample_rate=16000,  # Assuming 16kHz audio
            num_channels=1      # Assuming mono audio
        )])
        result = await self.pipeline_runner.run(task)
        
        # Get results from the different stages
        return {
            "transcription": result.transcription if hasattr(result, 'transcription') else "",
            "response": result.response if hasattr(result, 'response') else "",
            "audio": result.audio if hasattr(result, 'audio') else None
        }
