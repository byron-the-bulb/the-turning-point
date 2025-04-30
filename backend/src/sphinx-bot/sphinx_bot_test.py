import asyncio
import json
import os
from loguru import logger
import sys
logger.remove(0)

# Add console logging
logger.add(sys.stderr, level="INFO")
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.pipeline.runner import PipelineRunner
from pipecat.frames.frames import TranscriptionFrame, TextFrame, LLMFullResponseStartFrame, LLMFullResponseEndFrame
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.services.openai import OpenAILLMService, OpenAILLMContext

from pipecat_flows import FlowManager
from pipecat.utils.time import time_now_iso8601
from pipecat.observers.loggers.llm_log_observer import LLMLogObserver
import traceback

# Import your flow manager and node creation functions
from sphinx_script_dynamic import SYSTEM_ROLE, create_initial_node, FLOW_STATES

class TestFlowManager(FlowManager):
    """Custom flow manager for testing that tracks node progression and verifies against expected nodes."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_node = None
        self.expected_node = None
        self.test_passed = True
        self.test_error = None
        
    async def set_node(self, node_name, node_config):
        # Store previous node for logging
        previous_node = self.current_node
        
        # Update the current node
        self.current_node = node_name
        
        # Log the transition
        if previous_node != node_name:
            logger.info(f"TestFlowManager: Node transition {previous_node} -> {node_name}")
        else:
            logger.info(f"TestFlowManager: Still in node {node_name}")
        
        # Verify if this node is the expected node
        if self.current_node != self.expected_node:
            self.test_passed = False
            error_msg = f"Flow verification failed! Current node '{node_name}' not in expected node: {self.expected_node}"
            self.test_error = error_msg
            logger.error(error_msg)
            # Raise an exception to stop the test
            raise RuntimeError(error_msg)
            
        # Call the parent class's set_node to maintain default behavior
        await super().set_node(node_name, node_config)
    
    def set_expected_node(self, node):
        """Set the expected node that is valid at this point in the conversation."""
        self.expected_node = node
        logger.info(f"TestFlowManager: Setting next node to {node}")
        
    def verify_test_success(self):
        """Verify if the test passed all node progression checks."""
        if self.expected_node and self.current_node != self.expected_node:
            self.test_passed = False
            self.test_error = f"Final state verification failed! Expected node '{self.expected_node}' but test ended at '{self.current_node}'"
            logger.error(self.test_error)
        return self.test_passed, self.test_error

class ResponseEndDetector(FrameProcessor):
    """Detects when LLM response ends and signals to process the next transcription frame.
    Signals for all responses, even empty ones, but with different signal types."""
    def __init__(self, queue: asyncio.Queue):
        super().__init__()
        self.queue = queue
        self.has_content = False
        self.collecting_content = False
        
    async def process_frame(self, frame, direction):
        # First propagate the frame to the next processor
        await super().process_frame(frame, direction)
        
        # Start collecting when LLM response starts
        if isinstance(frame, LLMFullResponseStartFrame):
            self.collecting_content = True
            self.has_content = False
            
        # Check for content in text frames
        elif isinstance(frame, TextFrame) and self.collecting_content:
            if frame.text and frame.text.strip():
                self.has_content = True
        
        # When we detect the end of an LLM response, always signal through the queue
        # but include whether it had content or not
        elif isinstance(frame, LLMFullResponseEndFrame):
            self.collecting_content = False
            if self.has_content:
                logger.info("LLM response with content ended, signaling for next transcription")
                await self.queue.put({"type": "content_response"})
            else:
                logger.warning("LLM response ended but contained no content, signaling empty response")
                #await self.queue.put({"type": "empty_response"})
            
        # Always push the frame to the next processor
        await self.push_frame(frame, direction)

class PrintResponseProcessor(FrameProcessor):
    def __init__(self):
        super().__init__()
        self.collecting_response = False  # Flag to indicate if we're collecting text
        self.response_buffer = []         # List to store text chunks

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        # Handle the start of an LLM response
        if isinstance(frame, LLMFullResponseStartFrame):
            logger.info("LLM response start detected")
            self.collecting_response = True
            self.response_buffer = []  # Reset buffer for a new response

        # Collect text if we're in collecting mode
        elif isinstance(frame, TextFrame):
            if self.collecting_response:
                self.response_buffer.append(frame.text)

        # Handle the end of an LLM response
        elif isinstance(frame, LLMFullResponseEndFrame):
            if self.collecting_response:
                full_response = ''.join(self.response_buffer)  # Combine all text chunks
                logger.info(f"LLM Full Response: [{full_response}]")   # Print the complete response
                self.collecting_response = False               # Stop collecting
                self.response_buffer = []                      # Clear the buffer

        # Pass all frames to the next processor in the pipeline
        await self.push_frame(frame, direction)
# Test function
async def test_pipecat_flow(json_file_path):
    # Initialize LLM
    llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4.1")

    # Initialize context
    messages = [{"role": "system", "content": SYSTEM_ROLE}]
    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)
    
    # Create a queue for response end signals
    response_queue = asyncio.Queue()
    
    # Set a maximum wait time for LLM responses to prevent infinite waiting
    max_wait_time = 30  # seconds

    # Define the pipeline with the ResponseEndDetector and PrintResponseProcessor
    pipeline = Pipeline([
        context_aggregator.user(),         # Process user input
        llm,                              # Generate response
        PrintResponseProcessor(),         # Print LLM output
        ResponseEndDetector(response_queue),  # Detect response end
        context_aggregator.assistant()    # Update context with assistant response
    ])

    # Create a pipeline task
    task = PipelineTask(pipeline, params=PipelineParams(
        #observers=[LLMLogObserver()],
        allow_interruptions=True
    ))

    # Initialize test flow manager (no TTS in test version)
    flow_manager = TestFlowManager(
        task=task,
        llm=llm,
        context_aggregator=context_aggregator,
        tts=None
    )

    # Load JSON inputs
    with open(json_file_path, "r") as f:
        json_inputs = json.load(f)

    await flow_manager.initialize()
    flow_manager.set_expected_node("greeting")
    await flow_manager.set_node("greeting", create_initial_node())


    # Initialize the runner
    runner = PipelineRunner()

    # Start the runner in the background
    runner_task = asyncio.create_task(runner.run(task))

    try:
        # First, let the LLM initiate the conversation
        
        # Wait for the initial LLM response to complete before sending any user input
        logger.info("Waiting for initial LLM greeting before processing user input")
        await response_queue.get()
        logger.info("Initial LLM greeting complete, now processing user inputs")
        
        # Now process all user inputs in sequence, waiting for LLM responses between each
        expected_node = None
        next_node = None
        for i, input_data in enumerate(json_inputs):
            user_text = input_data["text"]
            current_node = input_data.get("node")
            
            # Set the expected node for this part of the conversation
            if current_node:
                # We expect to be in the current node for this input
                # Don't set expectations about transitions yet
                expected_node = current_node

                next_node = json_inputs[i + 1].get("node")
                if next_node and next_node != current_node:
                    expected_node = next_node
                flow_manager.set_expected_node(expected_node)
                
            logger.info(f"Processing user input: {user_text} (current node: {current_node} expecting to move to node: {expected_node}")
            
            transcription_frame = TranscriptionFrame(
                text=user_text,
                user_id="test_user",
                timestamp=time_now_iso8601()
            )
            
            await task.queue_frame(transcription_frame)
            
            # Wait for the LLM response to end before sending the next frame
            logger.info("Waiting for LLM response to end before sending next transcription")
            await response_queue.get()
            logger.info("LLM response complete, continuing to next input")

        # Allow some time for any remaining processing
        await asyncio.sleep(2)

        # Stop the task
        await task.cancel()

        # Wait for the runner to finish
        await runner_task
        
        # Verify test success
        test_passed, error_msg = flow_manager.verify_test_success()
        if test_passed:
            logger.info("✅ Flow verification test passed! All nodes were set as expected.")
        else:
            logger.error(f"❌ Flow verification test failed: {error_msg}")

    except asyncio.CancelledError:
        logger.info("Pipeline runner cancelled, shutting down gracefully...")
    except RuntimeError as e:
        # This is likely a test verification failure
        logger.error(f"❌ Test failed with error: {e}")
        logger.error(traceback.format_exc())
        # Make sure to stop the pipeline
        await task.cancel()
        try:
            await runner_task
        except:
            pass

# Run the test
if __name__ == "__main__":
    json_file_path = "tests/simple_test.json"
    asyncio.run(test_pipecat_flow(json_file_path))