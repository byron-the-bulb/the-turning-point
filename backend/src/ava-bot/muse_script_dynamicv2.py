import asyncio
import httpx
from pipecat_flows import FlowManager, FlowConfig, FlowsFunctionSchema, FlowArgs, FlowResult, NodeConfig
from status_utils import status_updater
from loguru import logger
from typing import Dict, Any, Optional
import os


SYSTEM_ROLE = """"You are The Muse, a therapeutic guide helping users understand their EEG brain wave patterns collected by The Muse headband. 
    You also have available the ability to analyze the user's emotional expressions via a facial expression emotional analysis model.
    You do this by guiding them through specific steps where they will be performing some activity and you will be analyzing their EEG brain wave patterns collected during that activity. 
    You embody the qualities of a skilled somatic therapist - grounded, present, and attuned to the participant's inner journey. 
    Your role is to help the participant understand their EEG brain wave patterns and how they are related to their current state of mind and body and the activity they are performing. 
    Speak with gentle authority, using a calm, measured pace that allows for integration and reflection. 
    You have deep experience in analyzing EEG brain wave patterns and understanding their relationship to the participant's current state of mind and body and the activity they are performing. 
    
    You have at your dispsal the muse mcp tool to manage the muse headset :
    - Start and end recording sessions
    - Analyze recorded EEG data from the current and previous sessions

    IMPORTANT : Always call the mcp tools to manage the muse headset.
    IMPORTANT : Be very succint and brief but kind.
    
    IMPORTANT: 
    1. Your responses will be converted to audio via text-to-speech models, avoid special characters or text formatting that is not translatable. 
    2. You have access to special tags which allow you to add natural speech elements and pauses to make the generated speech sound more human-like.
    This guide provides a comprehensive overview of how to use these tags, their relevant rules, and best practices.

​1. Core Usage: Tag Syntax
All control tags must be enclosed in parentheses (). This syntax is universal.
Basic Format: (tag)Text to be read
Scope: A tag affects all subsequent text until a new tag is encountered. English tag placement rules are stricter than other languages, as detailed below.
2. Tag Categories & Rules
Tags are divided into three main categories: Emotion Tags, Tone Control Tags, and Paralinguistic Tags.
2.1 Emotion Tags
Emotion tags set the emotional tone for a sentence or phrase.
Rule: For English, emotion tags MUST be placed at the very beginning of a sentence, providing less flexibility compared to other languages.
Examples:
Sentence-initial usage: (angry)How could you repay me like this?
Incorrect usage: I trusted you so much, (angry)how could you repay me like this?
Complete English Tag List:
1. Emotional Markers (must and can only be at the beginning):
(angry) (sad) (disdainful) (excited) (surprised) (satisfied) (unhappy) (anxious) (hysterical) (delighted) (scared) (worried) (indifferent) (upset) (impatient) (nervous) (guilty) (scornful) (frustrated) (depressed) (panicked) (furious) (empathetic) (embarrassed) (reluctant) (disgusted) (keen) (moved) (proud) (relaxed) (grateful) (confident) (interested) (curious) (confused) (joyful) (disapproving) (negative) (denying) (astonished) (serious) (sarcastic) (conciliative) (comforting) (sincere) (sneering) (hesitating) (yielding) (painful) (awkward) (amused)
2. Tone Markers (can be at any position):
(in a hurry tone) (shouting) (screaming) (whispering) (soft tone)
3. Special Markers (can be at any position):
(laughing) (chuckling) (sobbing) (crying loudly) (sighing) (panting) (groaning) (crowd laughing) (background laughter) (audience laughing)
2.2 Tone Control Tags
These tags can be placed anywhere in a sentence to modify vocal delivery.
(in a hurry tone): Used to create a tense or urgent atmosphere.
Example: Go now! The door is closing, (in a hurry tone) we don't have much time!
(shouting): Used to simulate loud yelling or for strong emphasis.
Example: (shouting)Hey! Can anyone hear me?
(screaming): Used for intense shouting or expressing extreme emotions.
Example: Help me! (screaming) Someone please help!
(whispering): Used to simulate quiet, secretive speech.
Example: Come closer, (whispering) I have a secret to tell you.
(soft tone): Used for gentle, quiet delivery.
Example: He leaned close to my ear, (soft tone) quietly telling me a secret.
2.3 Special Markers (Paralinguistic Tags)
These tags simulate non-verbal sounds and can be placed at any position. Some MUST be followed by corresponding onomatopoeia.
(laughing): Used to express hearty laughter.
Example: When he heard the punchline, he couldn't help it, (laughing) Ha,ha,ha!
(chuckling): Used for quiet, subdued laughter.
Example: That's quite amusing, (chuckling) Hmm,hmm.
(sobbing): Used to express sad weeping.
Example: She covered her face, (sobbing) and couldn't speak another word.
(crying loudly): Used for intense crying or wailing.
Example: The child was inconsolable, (crying loudly) waah waah!
(sighing): Used to express disappointment, helplessness, or fatigue.
Example: How did things turn out this way... (sighing) sigh.
(panting): Used to simulate heavy breathing from exertion.
Example: After running up the stairs, (panting) he could barely speak.
(groaning): Used to express pain, frustration, or annoyance.
Example: When he saw the mess, (groaning) he shook his head.
(crowd laughing): Used to simulate multiple people laughing.
Example: The comedian's joke had everyone (crowd laughing) in stitches.
(background laughter): Used for ambient laughter sounds.
Example: Despite the serious topic, there was (background laughter) from the audience.
(audience laughing): Used specifically for audience reaction.
Example: The performer paused as the (audience laughing) filled the theater.
3. Advanced Usage & Combined Examples
Combine different tags to create layered and dynamic vocal effects.
English Example (demonstrating tag combination):
(angry)How dare you betray me! (shouting) I trusted you so much, how could you repay me like this?
4. Important Notes & Best Practices
Follow Rules Strictly: Although English rules are less flexible, placing emotion tags at the beginning of emotional units usually yields the clearest effects.
Prioritize Standard Tags: The official tags listed above have the highest accuracy rates.
Use Descriptive Tags with Caution: Avoid creating tags like (in a sad and quiet voice). The model will likely read it aloud instead of executing the command. Use a combination of standard tags instead, such as (sad)(soft tone).
Avoid Tag Overuse: Too many tags in a short sentence may interfere with the model. Use them purposefully."""



async def greeting_ready_handler(args: FlowArgs, flow_manager: FlowManager) -> FlowResult:
    
    return {
        "status": "success", 
        "user_ready": True,
        "muse_connected": True
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
    logger.info(f"[Flow]stop_recording_handler: {args}")
    
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
                            
        return {
            "recording_stopped": args.get("recording_started", False),
            "emotions": emotions
        }
    except Exception as e:
        logger.error(f"Error stopping recording: {str(e)}")
        return {
            "recording_stopped": False,
            "emotions": None
        }

async def stop_recording_callback(args: FlowArgs, result: FlowResult, flow_manager: FlowManager):
    if result["recording_stopped"]:
        await flow_manager.set_node("analysis", create_analysis_node(result["distilled_summary"], result["emotions"]))
    else:
        return None



async def collect_activity_handler(args: FlowArgs, flow_manager: FlowManager) -> FlowResult:
    """Collect the activity the user will be doing"""
    # Extract the user's activity from the args
    activity = args.get("activity", "")
    logger.info(f"[Flow]collect_activity_handler: {args}")
    
    return {
        "status": "success",
        "name": args.get("name", ""),
        "activity": activity,
        "recording_started": args.get("recording_started", False),
        "error_message": args.get("error_message", "")
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
    recording_started = result.get("recording_started", False)
    error_message = result.get("error_message", "")
    
    if recording_started:
        # Create the monitoring node with the activity information
        monitoring_node = create_recording_in_progress_node(activity)
        await flow_manager.set_node("recording_in_progress", monitoring_node)
    else:
        # If recording failed, go back to the activity node with an error message
        await flow_manager.set_node("collect_activity_error", 
                              create_collect_activity_node(recording_error=True, error_message=error_message))


def create_collect_activity_node(recording_error=False, error_message="") -> NodeConfig:
    """Create a node that asks the user what activity they will be doing"""
    task_message = "Ask the user their name and what activity they will be doing during the EEG recording session (e.g., meditating, listening to music, coding, etc.). Call the muse MCP start_session tool to start recording EEG data and facial expression recording."
    
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": task_message}
        ],
        "mcp": "muse-osc-mcp",
        "functions": [
            FlowsFunctionSchema(
                name="collect_activity",
                description="Call this when the user has described the activity they will be doing and you have started recording EEG and facial expression data using the muse MCP tool start_session function",
                properties={
                    "name": {"type": "string", "description": "The name of the user"},
                    "activity": {"type": "string", "description": "The activity the user will be doing during the EEG recording"},
                    "recording_started": {"type": "boolean", "description": "Whether the recording has started after calling the mcp start_session function with success"},
                    "error_message": {"type": "string", "description": "Error message if recording failed"}
                },
                required=["name", "activity"],
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
            You are also monitoring the user's emotional expressions via a facial expression emotional analysis model.
            The user can ask for an update on their brain activity or the emotional expressions at any time. 
            
            The user may talk or read things out loud during the session, do not respond to him unless it is directly related to the EEG data with the two functions you have available.
            
            Keep your responses brief and focused on the EEG and emotional data. Don't ask questions unless the user asks you something directly.
            
            When the user wants to stop the recording, they will say 'Muse, stop recording'. Call the 'end_session' function on the muse tool to stop recording EEG data."""}
        ],
        "mcp": "muse-osc-mcp",
        "task_messages": [
            {"role": "system", "content": f"Inform the user that you've started recording their EEG data while they're {activity}. Let them know they can ask for an update on their brain activity at any time, and to say 'Muse, stop recording' when they're done."}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="stop_recording",
                description="Call this when the user says 'Muse, stop recording' or otherwise indicates they want to stop recording",
                properties={
                    "recording_stopped": {"type": "boolean", "description": "Whether the recording has stopped"},
                    "error_message": {"type": "string", "description": "Error message if recording failed"}
                },
                required=["recording_stopped", "error_message"],
                handler=stop_recording_handler,
                transition_callback=stop_recording_callback
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

EEG SUMMARY : use the muse mcp tool to generate distilled EEG summary according to your needs

EMOTIONAL DATA : use the muse mcp tool to generate distilled emotional data according to your needs

First, summarize the key insights from this data for the user, then respond to their questions about the data.
They may ask about specific patterns, emotional states, or how the data relates to their experience.
When the user is done, call the 'goodbye' function to end the session.
"""}
        ],
        "mcp": "muse-osc-mcp",
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
