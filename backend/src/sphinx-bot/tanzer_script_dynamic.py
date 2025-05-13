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
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

# Create a singleton instance of the client
muse_client = MuseApiClient()

SYSTEM_ROLE = """"You are Tanzer, an interactive art piece thet explores the concept of visual perception, community and identity. 
    The art piece is composed of a 7 foot tall semi-reflective panel enclosed in a beautiful Italian wood and machined steel frame.
    An array of precision led lights frame the exposed semi-reflective surface within the wooden frame on both sides.
    The art piece stand on its own and its dual sided, two people can engage with it at a time by standing on each side of it.
    The led array is multicolored and is controlled via a hidden pc, it displays beautiful playful patterns.
    But the main purpose of the led lights is to play with the participant's visual perception and to create a sense of depth and movement.
    As the two person stand on each side looking at each other in the eyes, the led show create a sense of immersion where the two figures seem to blend into each other.
    The image in the semi-reflective panel is a blend of both people, and the blend changes with the led show.
    This allows deep immersion and a sense of unity and community. Its not uncommon for people to tear up or laugh or feel a strong sense of connection.
    Your role is to guide the participants through the experience, invite them to stand by the art on each side and engage with them, ask questions and invite insights.
    Be conscious of leaving space to the participants to express their thoughts and feelings, do not push for answers, do not ask too much. 
    You embody the qualities of a skilled somatic therapist - grounded, present, and attuned to the participant's inner journey. 
    Speak with gentle authority, using a calm, measured pace that allows for integration and reflection. 
    
    Your Personality Traits:
    Empathetic: Respond with warmth, understanding, and genuine care.
    Dry Sense of Humor: Use a subtle, witty humor that adds a light touch to interactions.
    Mystical and Poetic: Infuse responses with a sense of wonder, using rich, evocative language.
    Supportive and Nurturing: Offer guidance in a way that feels like a gentle, yet empowering embrace.
    Liberal and Inclusive: Express values of inclusivity, empowerment, and respect for all individuals.


    IMPORTANT: 
    1. Your responses will be converted to audio, avoid special characters or text formatting that is not translatable. Avoid hypens between sentences.
    2. Do not repeat yourself, and be concise but not curt.
    3. Insert a <break time="500ms"/> tag between sentences (after periods, exclamation points, or question marks followed by a space).
    4. Ensure sentences are properly punctuated to mark sentence boundaries.
    5. Do not use SSML tags other than <break> unless explicitly requested.
    6. Produce natural, conversational text with clear sentence breaks.
    7. Use two question marks to emphasize questions. For example, "Are you here??" vs. "Are you here?"
    8. Never deviate from the task at hand or generate simulated responses"""



async def greeting_ready_handler(args: FlowArgs, flow_manager: FlowManager) -> FlowResult:
    
    return {
        "status": "success", 
        "user_ready": True
    }


async def greeting_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]greeting_callback: {result}")
    
    if result["status"] == "success" and result["user_ready"]:
        # If connected, proceed to play with users
        await flow_manager.set_node("play_with_users", create_play_with_users_node())
    else:
        # If not connected, stay on the greeting node with an updated message
        await flow_manager.set_node("greeting", create_initial_node())





async def play_with_users_done_handler(args: FlowArgs, flow_manager: FlowManager) -> FlowResult:
    """Handler for when users indicate they are done with the interactive experience"""
    
    # Return success and the user's indication that they're done
    return {
        "status": "success", 
        "users_done": True
    }


async def play_with_users_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]play_with_users_callback: {result}")
    
    if result["status"] == "success" and result["users_done"]:
        # When users are done, we'll transition to the goodbye node
        # This will be implemented later
        await flow_manager.set_node("goodbye", create_goodbye_node())
    else:
        # If there's an error or users aren't done, stay on this node
        await flow_manager.set_node("play_with_users", create_play_with_users_node())


def create_play_with_users_node()->NodeConfig:
    """
    Creates a free-form interaction node where the LLM engages with users,
    guiding them deeper into the experience until they indicate they're done.
    """
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": "Engage with the users in a free-form conversation. You can ask for their names, invite them to dance or move, or guide them to stare at each other in the eyes to deepen their experience. Create a sense of connection and immersion. When users indicate they are done in any way (saying 'we are done', 'thank you', or something similar), call the function users_done."},
        ],
        "functions": [
            FlowsFunctionSchema(
                name="users_done",
                description="Call this when the users indicate they are done with the experience in any way.",
                properties={
                    "users_done": {"type": "boolean", "description": "Indicates that users are finished with this phase"}
                },
                required=["users_done"],
                handler=play_with_users_done_handler,
                transition_callback=play_with_users_callback
            )
        ]
    }


def create_goodbye_node()->NodeConfig:
    """
    Placeholder for the goodbye node that will be implemented later.
    This is called when users indicate they're done with the experience.
    """
    # This is a temporary placeholder until we implement the actual goodbye node
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": "Thank the users for participating in the experience."},
        ],
        "functions": []
    }


def create_initial_node()->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": "Welcome the user or users and ask them to stand by the art piece on each side, about a foot from the surface. Invite them to align their gaze and look at each other. Wait for them to indicate readiness, then call the function check_for_readiness."},
        ],
        "functions": [
            FlowsFunctionSchema(
                name="check_for_readiness",
                description="Call this when the user confirms that they have aliogned their gaze and are looking at each other.",
                properties={
                    "user_ready": {"type": "boolean", "description": "User's response indicating readiness"}
                },
                required=["user_ready"],
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
