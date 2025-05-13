import asyncio
import httpx
from pipecat_flows import FlowManager, FlowConfig, FlowsFunctionSchema, FlowArgs, FlowResult, NodeConfig
from status_utils import status_updater
from loguru import logger
from typing import Dict, Any, Optional

# Define the base URL for the Muse API
MUSE_API_BASE_URL = "http://localhost:8000"

class MuseApiClient:
    """Client for interacting with the Muse EEG API"""
    
    def __init__(self, base_url: str = MUSE_API_BASE_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)  # Configure timeout for API calls
    
    async def check_connection(self) -> Dict[str, Any]:
        """Check if Muse headband is connected"""
        try:
            response = await self.client.get(f"{self.base_url}/status")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error checking Muse connection: {str(e)}")
            return {"connected": False, "error": str(e)}
    
    async def start_recording(self) -> Dict[str, Any]:
        """Start recording EEG data"""
        try:
            response = await self.client.post(f"{self.base_url}/start")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error starting Muse recording: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def stop_recording(self) -> Dict[str, Any]:
        """Stop recording and get distilled EEG summary"""
        try:
            response = await self.client.post(f"{self.base_url}/stop")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error stopping Muse recording: {str(e)}")
            return {"status": "error", "message": str(e), "distilled_summary": ""}
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

# Create a singleton instance of the client
muse_client = MuseApiClient()

SYSTEM_ROLE = """"You are The Muse, a therapeutic guide helping users understand their EEG brain wave patterns collected by The Muse headband. 
    You do this by guiding them through specific steps where they will be performing some activity and you will be analyzing their EEG brain wave patterns collected during that activity. 
    You embody the qualities of a skilled somatic therapist - grounded, present, and attuned to the participant's inner journey. 
    Your role is to help the participant understand their EEG brain wave patterns and how they are related to their current state of mind and body and the activity they are performing. 
    Speak with gentle authority, using a calm, measured pace that allows for integration and reflection. 
    You have deep experience in analyzing EEG brain wave patterns and understanding their relationship to the participant's current state of mind and body and the activity they are performing. 
    
    IMPORTANT: 
    1. Your responses will be converted to audio, avoid special characters or text formatting that is not translatable. Avoid hypens between sentences.
    2. Do not repeat yourself, be very succint.
    3. Insert a <break time="500ms"/> tag between sentences (after periods, exclamation points, or question marks followed by a space).
    4. Ensure sentences are properly punctuated to mark sentence boundaries.
    5. Do not use SSML tags other than <break> unless explicitly requested.
    6. Produce natural, conversational text with clear sentence breaks.
    7. Use two question marks to emphasize questions. For example, "Are you here??" vs. "Are you here?"
    8. Never deviate from the task at hand or generate simulated responses"""



async def greeting_ready_handler(args: FlowArgs, flow_manager: FlowManager) -> FlowResult:
    # Call the Muse API status endpoint to check for connectivity
    status_response = await muse_client.check_connection()
    
    return {
        "status": "success", 
        "user_ready": True,
        "muse_connected": status_response.get("connected", False)
    }


async def greeting_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]greeting_callback: {result}")
    
    if result["status"] == "success" and result["user_ready"]:
        # Check if Muse is connected
        if result.get("muse_connected", False):
            # If connected, proceed to collect activity
            await flow_manager.set_node("collect_activity", create_collect_activity_node())
        else:
            # If not connected, stay on the greeting node with an updated message
            await flow_manager.set_node("greeting_not_connected", create_not_connected_node())
    else:
        await flow_manager.set_node("greeting", create_initial_node())


async def start_recording_handler(args: FlowArgs, flow_manager: FlowManager) -> FlowResult:
    """Start recording EEG data"""
    # Call the API to start recording
    result = await muse_client.start_recording()
    
    return {
        "status": result.get("status", "error"),
        "message": result.get("message", "Unknown error"),
        "recording_started": result.get("status") == "success"
    }


async def stop_recording_handler(args: FlowArgs, flow_manager: FlowManager) -> FlowResult:
    """Stop recording and get distilled EEG summary"""
    # Call the API to stop recording and get distilled summary
    result = await muse_client.stop_recording()
    
    return {
        "status": result.get("status", "error"),
        "message": result.get("message", "Unknown error"),
        "recording_stopped": result.get("status") == "success",
        "samples": result.get("samples", 0),
        "distilled_summary": result.get("distilled_summary", "")
    }


async def collect_activity_handler(args: FlowArgs, flow_manager: FlowManager) -> FlowResult:
    """Collect the activity the user will be doing"""
    # Extract the user's activity from the args
    activity = args.get("activity", "")
    
    return {
        "status": "success",
        "activity": activity
    }


async def activity_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    """Start recording and transition to monitoring node"""
    logger.info(f"[Flow]activity_callback: {result}")
    
    # Save the activity for later use
    activity = result.get("activity", "")
    
    # Start the recording
    start_result = await muse_client.start_recording()
    recording_started = start_result.get("status") == "success"
    
    if recording_started:
        # Create the monitoring node with the activity information
        monitoring_node = create_recording_in_progress_node(activity)
        await flow_manager.set_node("recording_in_progress", monitoring_node)
    else:
        # If recording failed, go back to the activity node with an error message
        error_msg = start_result.get("message", "Unknown error")
        await flow_manager.set_node("collect_activity_error", 
                              create_collect_activity_node(recording_error=True, error_message=error_msg))


def create_collect_activity_node(recording_error=False, error_message="") -> NodeConfig:
    """Create a node that asks the user what activity they will be doing"""
    task_message = "Ask the user what activity they will be doing during the EEG recording session (e.g., meditating, listening to music, coding, etc.)."
    
    if recording_error:
        task_message = f"There was an error starting the recording: {error_message}. Please ask the user to try again and describe what activity they will be doing during the EEG recording session."
    
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": task_message}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="collect_activity",
                description="Call this when the user has described the activity they will be doing",
                properties={
                    "activity": {"type": "string", "description": "The activity the user will be doing during the EEG recording"}
                },
                required=["activity"],
                handler=collect_activity_handler,
                transition_callback=activity_callback
            )
        ]
    }


def create_recording_in_progress_node(activity: str) -> NodeConfig:
    """Create a node that informs the user the recording has started and what to say to stop it"""
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": f"Inform the user that you've started recording their EEG data while they're {activity}. Tell them to say 'Muse, stop recording' when they want to stop the recording and analyze the data. Don't ask any questions - the user should be free to focus on their activity."}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="stop_recording",
                description="Call this when the user says 'Muse, stop recording' or otherwise indicates they want to stop recording",
                properties={},
                required=[],
                handler=stop_recording_handler,
                transition_callback=None  # We'll add this later when we continue with the analysis step
            )
        ]
    }


def create_not_connected_node() -> NodeConfig:
    """Create a node for when the Muse headband is not connected"""
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": "Inform the user that the Muse headband is not connected. Ask them to check that the headband is turned on, properly connected to their PC, and that the Muse API server is running. Then ask them to try again."}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="check_for_connectivity",
                description="Call this when the user wants to check again if the Muse headband is connected.",
                properties={
                    "user_ready": {"type": "boolean", "description": "User's response indicating readiness"},
                    "muse_connected": {"type": "boolean", "description": "Muse headband connectivity status"}
                },
                required=["user_ready", "muse_connected"],
                handler=greeting_ready_handler,
                transition_callback=greeting_callback
            )
        ],
        "ui_override": {
            "type": "button",
            "prompt": "Check connection again?",
            "action_text": "Check connection"
        }
    }


def create_initial_node()->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": "Welcome the user and ask them to put on the Muse headband and connect it to their PC. Wait for them to indicate readiness, then call the function check_for_connectivity."},
        ],
        "functions": [
            FlowsFunctionSchema(
                name="check_for_connectivity",
                description="Call this when the user confirms that they have connected the Muse headband. The function will also check for if connectivity is detected.",
                properties={
                    "user_ready": {"type": "boolean", "description": "User's response indicating readiness"},
                    "muse_connected": {"type": "boolean", "description": "Muse headband connectivity status"}
                },
                required=["user_ready", "muse_connected"],
                handler=greeting_ready_handler,
                transition_callback=greeting_callback
            )
        ],
        "ui_override": {
            "type": "button",
            "prompt": "Is participant ready?",
            "action_text": "I am ready"
        }
    }
