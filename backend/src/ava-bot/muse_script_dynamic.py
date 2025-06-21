import asyncio
import httpx
from pipecat_flows import FlowManager, FlowConfig, FlowsFunctionSchema, FlowArgs, FlowResult, NodeConfig
from status_utils import status_updater
from loguru import logger
from typing import Dict, Any, Optional
import os

# Define the base URL for the Muse API from .env
MUSE_API_BASE_URL = os.getenv("MUSE_API_BASE_URL", "http://localhost:8000")

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
    
    async def get_eeg_data(self, distill_window: float = 5.0) -> Dict[str, Any]:
        """
        Get distilled EEG data for the last 'distill_window' seconds
        
        Args:
            distill_window: Time window in seconds to distill EEG data from (default: 5.0)
            
        Returns:
            Dictionary containing the distilled EEG data or error information
        """
        try:
            params = {"distill_window": distill_window}
            response = await self.client.get(f"{self.base_url}/data", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting EEG data: {str(e)}")
            return {"status": "error", "message": str(e)}
    
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
    try:
        #if emotions are present in the flow manager state, add them to the return value
        if "prosody_emotions" in flow_manager.state:
            # process the emotions and only take the top 4 for each timestamp, sorted by score, return every timestamp
            emotions = flow_manager.state["prosody_emotions"]
            processed_emotions = []
            
            for emotion_entry in emotions:
                timestamp = emotion_entry.get("timestamp")
                emotions_data = emotion_entry.get("emotions", {})
                
                # Check if predictions exists and has content
                predictions = emotions_data.get("predictions", [])
                if predictions and isinstance(predictions, list):
                    for prediction in predictions:
                        if "emotions" in prediction and isinstance(prediction["emotions"], list):
                            # Sort emotions by score and take top 4
                            top_emotions = sorted(prediction["emotions"], key=lambda x: x.get("score", 0), reverse=True)[:4]
                            
                            # Create a processed entry with timestamp and top emotions
                            processed_entry = {
                                "timestamp": timestamp,
                                "time": prediction.get("time", {}),
                                "emotions": top_emotions
                            }
                            processed_emotions.append(processed_entry)
            
            logger.info(f"Processed emotions: {processed_emotions}")
            emotions = processed_emotions
        else:
            logger.info("No emotions found in flow manager state")
            emotions = None
                            
        result = await muse_client.stop_recording()
        return {
            "status": result.get("status", "error"),
            "message": result.get("message", "Unknown error"),
            "recording_stopped": result.get("status") == "success",
            "samples": result.get("samples", 0),
            "distilled_summary": result.get("distilled_summary", ""),
            "emotions": emotions
        }
    except Exception as e:
        logger.error(f"Error stopping recording: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "recording_stopped": False,
            "samples": 0,
            "distilled_summary": ""
        }

async def stop_recording_callback(args: FlowArgs, result: FlowResult, flow_manager: FlowManager):
    if result["status"] != "error":
        await flow_manager.set_node("analysis", create_analysis_node(result["distilled_summary"], result["emotions"]))
    else:
        return None


async def get_eeg_update_handler(args: FlowArgs, flow_manager: FlowManager) -> FlowResult:
    """Get current EEG data summary for the recording session"""
    try:
        # Get the duration from function args or use default 5.0 seconds
        duration = float(args.function_args.get("duration_seconds", 5.0))
        
        # Get the EEG data from the API
        eeg_data = await muse_client.get_eeg_data(distill_window=duration)
        
        if eeg_data.get("status") == "error":
            logger.error(f"Error getting EEG update: {eeg_data.get('message')}")
            return {"status": "error", "message": eeg_data.get("message", "Failed to get EEG update")}
            
        # Include the activity if provided in the function call
        activity = args.function_args.get("activity", "")
        if activity:
            eeg_data["activity"] = activity
            
        return {"status": "success", "eeg_data": eeg_data}
        
    except Exception as e:
        logger.error(f"Error in get_eeg_update_handler: {str(e)}")
        return {"status": "error", "message": str(e)}


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
            {"role": "system", "content": f"""You are currently monitoring the user's EEG data while they are {activity}.
            You are also monitoring the user's emotional state via a voice prosody emotional analysis model.
            Emotions will only be made available to you when the user stops the recording.
            The user can ask for an update on their brain activity at any time. When they do, call the 'get_eeg_update' function to get the latest EEG data.
            
            If the user mentions any specific activity or state change (like 'I just started meditating' or 'I'm feeling more relaxed now'), include that as the 'activity' parameter when calling get_eeg_update.

            The user may talk or read things out loud during the session, do not respond to him unless it is directly related to the EEG data with the two functions you have available.
            
            Keep your responses brief and focused on the EEG data. Don't ask questions unless the user asks you something directly.
            
            When the user wants to stop the recording, they will say 'Muse, stop recording'."""}
        ],
        "task_messages": [
            {"role": "system", "content": f"Inform the user that you've started recording their EEG data while they're {activity}. Let them know they can ask for an update on their brain activity at any time, and to say 'Muse, stop recording' when they're done."}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="stop_recording",
                description="Call this when the user says 'Muse, stop recording' or otherwise indicates they want to stop recording",
                properties={},
                required=[],
                handler=stop_recording_handler,
                transition_callback=stop_recording_callback
            ),
            FlowsFunctionSchema(
                name="get_eeg_update",
                description="Call this to get the latest EEG data summary. Use when the user asks for an update on their brain activity or when they mention a change in their mental/emotional state.",
                properties={
                    "activity": {
                        "type": "string",
                        "description": "Optional: The current activity or mental/emotional state the user is reporting (e.g., 'meditating', 'focused', 'relaxed', 'distracted')"
                    },
                    "duration_seconds": {
                        "type": "number",
                        "description": "Optional: Time window in seconds to analyze (default: 5.0)"
                    }
                },
                required=[],
                handler=get_eeg_update_handler
            )
        ]
    }

async def goodbye_handler(args : FlowArgs):
    """Handle the 'goodbye' function"""
    return {
        "status": "success",
        "message": "Goodbye"
    }

def create_analysis_node(eeg_summary, emotions) -> NodeConfig:
    """Create a node for analyzing the recorded EEG and emotion data"""
    return {
        "task_messages": [
            {"role": "system", "content": f"""You are now analyzing the user's EEG and emotional data from their recent recording session. 
Help them understand patterns in their brain activity and emotions, answering any questions they might have about the data.

EEG SUMMARY:
{eeg_summary if eeg_summary else 'No EEG data available'}

EMOTIONAL DATA:
{str(emotions) if emotions else 'No emotional data available'}

First, summarize the key insights from this data for the user, then respond to their questions about the data.
They may ask about specific patterns, emotional states, or how the data relates to their experience.
When the user is done, call the 'goodbye' function to end the session.
"""}
        ],
    "functions": [
        FlowsFunctionSchema(
            name="goodbye",
            description="Call this when the user is done analyzing the EEG and emotional data.",
            properties={},
            required=[],
            handler=goodbye_handler,
            transition_callback=None
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
        ]
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
        ]
    }
