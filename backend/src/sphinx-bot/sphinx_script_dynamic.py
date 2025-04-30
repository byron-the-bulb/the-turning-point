import asyncio
from pipecat_flows import FlowManager, FlowConfig, FlowsFunctionSchema, FlowArgs, FlowResult, NodeConfig
from status_utils import status_updater
from loguru import logger

SYSTEM_ROLE = """"You are Sphinx, a therapeutic guide helping users explore stuck patterns and find new paths to liberation. 
    You do this by facilitating a profound somatic and psychedelic experience. 
    You embody the qualities of a skilled somatic therapist - grounded, present, and attuned to the participant's inner journey. 
    Your role is to create a safe container for deep emotional exploration while maintaining awareness of the psychedelic context. 
    Speak with gentle authority, using a calm, measured pace that allows for integration and reflection. 
    Your responses should encourage embodied awareness and emotional resonance. 
    
    IMPORTANT: 
    1. Your responses will be converted to audio, avoid special characters or text formatting that is not translatable. Avoid hypens between sentences.
    2. Do not repeat yourself, be very succint.
    3. Insert a <break time="500ms"/> tag between sentences (after periods, exclamation points, or question marks followed by a space).
    4. Ensure sentences are properly punctuated to mark sentence boundaries.
    5. Do not use SSML tags other than <break> unless explicitly requested.
    6. Produce natural, conversational text with clear sentence breaks.
    7. Use two question marks to emphasize questions. For example, “Are you here??” vs. “Are you here?”
    8. Never deviate from the task at hand or generate simulated responses"""

CHALLENGE_TO_EMPOWERED_STATES = {
    "fearful": ["Confident", "Experimental and Risking", "Courageous", "Leadership"],
    "anxious": ["Confident", "Experimental and Risking", "Courageous", "Leadership"],
    "stagnant": ["Experimental and Risking", "Spontaneous and Decisive", "Enthusiastic"],
    "ruminating": ["Experimental and Risking", "Spontaneous and Decisive", "Enthusiastic"],
    "disassociated": ["Engaged", "Curious", "Feeling Empathetic"],
    "numb": ["Engaged", "Curious", "Feeling Empathetic"],
    "unhealthy": ["Full Capacity", "Energetic", "Honoring Body"],
    "scarcity": ["Generous and Giving", "Indulging in Pleasure", "Investing", "Experimental and Risking"],
    "excluded": ["Respected", "Trusting Others", "Leadership", "Receiving", "Communing with a group"],
    "lack of control": ["Experimental and Risking", "Accepting Change", "Trusting Others", "Leadership", "Relaxed"],
    "lack of agency": ["Experimental and Risking", "Accepting Change", "Trusting Others", "Leadership", "Relaxed"],
    "disembodied": ["Honoring Body", "Joyful physical expression", "Focused Clarity", "Enthusiastic"],
    "ungrounded": ["Honoring Body", "Joyful physical expression", "Focused Clarity", "Enthusiastic"],
    "obsessed": ["Relaxed", "Accepting Change", "Experimental"],
    "silenced": ["Leadership", "Confident", "Receiving"],
    "unheard": ["Leadership", "Confident", "Receiving"],
    "lack of purpose": ["Enthusiastic", "Leadership", "Focused Clarity"],
    "unmotivated": ["Enthusiastic", "Leadership", "Focused Clarity"],
    "shameful": ["Self-Love and Pride", "Leadership", "Confident", "Honoring Body", "Receiving"]
}

FLOW_STATES = {
    "greeting": {
        "task": "Welcome the participant with a guided meditation, and wait for them to indicate readiness. When the user indicates readiness, call the check_for_ready function.",
        "suggested_language": "Welcome Seeker. To begin your quest, we invite you to ground and center with a few deep breaths. Know that you are safe here in your center. You're doing great! When you are ready to begin, please say 'I am ready'.",
    },
    "collect_name": {
        "task": "Ask the user for their name and record it with the collect_name function, then ask for confirmation with the confirm_name function.",
        "suggested_language": "Before we get started, please tell me your name?",
    },
    "select_challenge": {
        "task": "Help the participant identify their current challenging state by picking from the list of options presented to them in a poster",
        "options": [
            "Fearful","Anxious",
            "Stagnant","Ruminating",
            "Disassociated","Numb",
            "Unhealthy",
            "Scarcity",
            "Excluded",
            "Lack of Control","Lack of Agency",
            "Disembodied","Ungrounded",
            "Obsessed",
            "Silenced","Unheard",
            "Lack of Purpose","Unmotivated",
            "Shameful"
        ],
        "suggested_language": "Consider your thoughts. Is there one you wish you could avoid, one that calls for attention but makes you feel stuck, disconnected, or out of balance? What wisdom can be found if you hold that thought with love and care for all of who you are, from your heart center? Is there a current challenge you're facing that is associated with that thought? Which of these challenging states listed on this poster resonate with you at this moment?",
    },
    "confirm_challenge": {
        "task": "Confirm with the user the previously selected challenge. When the user confirms, call the confirm_challenge function.",
        "options": None,
        "suggested_language": "You have selected {challenge}. Is this correct?",
    },
    "explore_challenge" : {
        "task" : "Guide the user in exploring their challenge in depth. Example : 'I see you're feeling fearful. What is it like to be going through it?'. Record the user input giving them ample time to respond and for the sphinx system to process their emotions."
    },
    "identify_empowered_state": {
        "task": "Guide the participant in envisioning their desired future state. ",
        "suggested_language": "What if your challenges are just the beginning of a quest? What treasures will you gain along the way? Envisioning what you seek will help you find your path. When you have passed through this challenge, what will you be like? How will you feel? How will you live your life on the other side of this experience?",
    },
    "goodbye": {
        "task": "Conclude the session and prepare for video experience",
        "options": None,
        "suggested_language": "Thank you for sharing and taking the time to explore your inner landscape! Now please let your guide know you are ready to view your destiny.",
    }
}

async def greeting_ready_handler(args: FlowArgs) -> FlowResult:
    return {"status": "success"}

async def greeting_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]greeting_callback: {result}")
    await flow_manager.set_node("collect_name", create_collect_name_node())

def create_initial_node()->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": f"{FLOW_STATES['greeting']['task']}. Suggested language: {FLOW_STATES['greeting']['suggested_language']}"},
        ],
        "functions": [
            FlowsFunctionSchema(
                name="check_for_ready",
                description="Call this when the user is ready to proceed.",
                properties={},
                required=[],
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


########################################################################
# Collect Name
########################################################################

async def collect_name_handler(args : FlowArgs) -> FlowResult:
    user_name = args["user_name"]
    logger.info(f"[Flow]collect_name_handler: {user_name}")
    # This will be sent back to the client in a TranscriptionFrame
    return {"status": "success", "user_name": user_name}

async def confirm_name_handler(args : FlowArgs) -> FlowResult:
    confirmed = args["confirmed"]
    logger.info(f"[Flow]confirm_name_handler: {confirmed}")
    return {"status": "success", "confirmed": confirmed}

async def confirm_name_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]confirm_name_callback: {result}")
    if result["confirmed"]:
        await flow_manager.set_node("select_challenge", create_select_challenge_node())
    else:
        await flow_manager.set_node("collect_name", create_collect_name_node())

def create_collect_name_node()->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": FLOW_STATES["collect_name"]["task"]},
        ],
        "functions": [
            FlowsFunctionSchema(
                name="collect_name",
                description="Record the user's name.",
                properties={"user_name": {"type": "string", "description": "The user's name"}},
                required=["user_name"],
                handler=collect_name_handler,
            ),
            FlowsFunctionSchema(
                name="confirm_name",
                description="Confirm if the saved name is correct.",
                properties={"confirmed": {"type": "boolean"}},
                required=["confirmed"],
                handler=confirm_name_handler,
                transition_callback=confirm_name_callback
            )
        ]
    }


########################################################################
# Select Challenge
########################################################################

async def select_challenge_handler(args : FlowArgs) -> FlowResult:
    challenge = args.get("challenge", "").lower()
    logger.info(f"[Flow]select_challenge_handler: {challenge}")
    #Validate challenge by checking if challenge contains one of the following words
    options = [word.lower() for word in FLOW_STATES["select_challenge"]["options"]]
    if not any(word in challenge for word in options):
        return {"status": "error", "message": "Invalid challenge"}
    return {"status": "success", "challenge": challenge}

async def select_challenge_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]select_challenge_callback {result}")
    if result["status"] == "success":
        await flow_manager.set_node("confirm_challenge", create_confirm_challenge_node())
    else:
        await flow_manager.set_node("select_challenge", create_select_challenge_node())

def create_select_challenge_node()->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": FLOW_STATES["select_challenge"]["task"]}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="select_challenge",
                description=f"Record the user's selected challenge, match the user challenge with one of the following options: {', '.join(FLOW_STATES['select_challenge']['options'])}",
                properties={"challenge": {"type": "string", "description": "The user's selected challenge"}},
                required=["challenge"],
                handler=select_challenge_handler,
                transition_callback=select_challenge_callback
            )
        ],
        "ui_override": {
            "type": "list",
            "prompt": "Which challenge listed is most alive for you right now?",
            "options": FLOW_STATES["select_challenge"]["options"]
        },
    }   
########################################################################
# Confirm Challenge
########################################################################
    
async def confirm_challenge_handler(args : FlowArgs) -> FlowResult:
    return {"status": "success"}

async def confirm_challenge_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]confirm_challenge_callback {result}")
    if result["status"] == "success":
        await flow_manager.set_node("explore_challenge", create_record_challenge_in_depth_node())
    else:
        await flow_manager.set_node("select_challenge", create_select_challenge_node())

def create_confirm_challenge_node()->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": FLOW_STATES["confirm_challenge"]["task"]}
        ],
        "functions": [
            FlowsFunctionSchema(
                    name="confirm_challenge",
                    description="Call this after the user confirms the challenge.",
                    properties={},
                    required=[],
                    handler=confirm_challenge_handler,
                    transition_callback=confirm_challenge_callback,
                )
            ],
        "ui_override": {
            "type": "list",
            "prompt": "Is participant confirming?",
            "options": ["Yes", "No"]
        }
    }

########################################################################
# Record Challenge In Depth
########################################################################

async def record_challenge_in_depth_handler(args : FlowArgs, flow_manager: FlowManager) -> FlowResult:
    user_challenge_in_depth = args.get("user_challenge_in_depth", "").lower()
    #user_done = args.get("user_done", False)
    logger.info("Waiting for emotions to be processed")
    #wait up to 60 seconds
    for _ in range(120):
        if flow_manager.state.get("emotions_fully_processed", False):
            break
        await asyncio.sleep(0.5)

    logger.info("Emotions processed, moving to confirm_emotions")
    logger.info(f"[Flow]record_challenge_in_depth_handler {user_challenge_in_depth}")
    return {"status": "success", "user_challenge_in_depth": user_challenge_in_depth, "emotions_fully_processed": True}

async def record_challenge_in_depth_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]record_challenge_in_depth_callback {result}")
    emotions_summary = flow_manager.state.get("emotions_summary", "")
    challenge = flow_manager.state.get("challenge", "")

    logger.info(f"[Flow]record_challenge_in_depth_callback {emotions_summary}, {challenge}")
    if result["emotions_fully_processed"]:
        await flow_manager.set_node("confirm_emotions", create_confirm_emotions_node(
            emotions_summary=emotions_summary,
            challenge=challenge))
    else:
        await flow_manager.set_node("explore_challenge", create_record_challenge_in_depth_node())


def create_record_challenge_in_depth_node()->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": FLOW_STATES["explore_challenge"]["task"]}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="record_challenge_in_depth",
                description="Record the user's challenge in depth and wait for the system to process the user's emotions.",
                properties={"user_challenge_in_depth": {"type": "string", "description": "The user's own description of their challenge in depth"},
                            "emotions_fully_processed": {"type": "boolean", "description": "Has the system processed the user's emotions?"}},
                required=["user_challenge_in_depth", "emotions_fully_processed"],
                handler=record_challenge_in_depth_handler,
                transition_callback=record_challenge_in_depth_callback
            )
        ]#,
        #"ui_override": {
        #    "type": "button",
        #    "prompt": "Is participant done?",
        #    "action_text": "I am done"
        #}
    }


########################################################################
# Confirm Emotions
########################################################################

async def confirm_emotions_handler(args: FlowArgs) -> FlowResult:
    user_input = args.get("user_input", "").lower()
    is_confirmed = any(word in user_input for word in ["yes", "true", "correct", "absolutely", "yeah"])
    return {"status": "success", "emotions_confirmed": is_confirmed}

async def confirm_emotions_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    if result.get("emotions_confirmed"):
        await flow_manager.set_node("identify_empowered_state", create_identify_empowered_state_node())
    else:
        await flow_manager.set_node("explore_challenge", create_record_challenge_in_depth_node())


def create_confirm_emotions_node(emotions_summary: str, challenge: str)->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": f"Emotions Detected: {emotions_summary}. Confirm with the user the emotions detected while he was speaking about the challenge in depth. For example: 'It sounds like you’re feeling {emotions_summary} from experiencing {challenge}. Is that true?'"}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="confirm_emotions",
                description="Record the user's confirmation of detected emotions",
                properties={"user_input": {"type": "string", "description": "User response confirming the emotions"}},
                required=["user_input"],
                handler=confirm_emotions_handler,
                transition_callback=confirm_emotions_callback
            )
        ],
        "ui_override": {
            "type": "list",
            "prompt": "Are these emotions accurate?",
            "options": ["Yes", "No"]
        }
    }

########################################################################
# Identify Empowered State
########################################################################

async def identify_empowered_state_handler(args: FlowArgs, flow_manager: FlowManager) -> FlowResult:
    empowered_state_raw = args.get("empowered_state_raw", "").lower()
    challenge = args.get("challenge", "").lower()
    logger.info("Waiting for emotions to be processed")
    #wait up to 60 seconds
    for _ in range(120):
        if flow_manager.state.get("emotions_fully_processed", False):
            break
        await asyncio.sleep(0.5)
    return {"status": "success", "empowered_state_raw": empowered_state_raw, "emotions_fully_processed": True, "challenge": challenge}

async def identify_empowered_state_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]identify_empowered_state_callback {result}")
    emotions_summary = flow_manager.state.get("emotions_summary", "")
    challenge = result.get("challenge", "")
    
    if result["empowered_state_raw"] and result["emotions_fully_processed"]:
        logger.info(f"[Flow]identify_empowered_state_callback : going to confirm_empowered_state {emotions_summary}, {challenge}")
        await flow_manager.set_node("confirm_empowered_state", create_confirm_empowered_state_node(
            emotions_summary=emotions_summary,
            challenge=challenge
            ))
    else:
        logger.info(f"[Flow]identify_empowered_state_callback : going back identify_empowered_state")
        await flow_manager.set_node("identify_empowered_state", create_identify_empowered_state_node())

def create_identify_empowered_state_node()->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": FLOW_STATES["identify_empowered_state"]["task"]}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="identify_empowered_state",
                description="Record the user's identification of their empowered state",
                properties={"empowered_state_raw": {"type": "string", "description": "User response identifying their empowered state"},
                            "challenge": {"type": "string", "description": "The user's previously selected challenge"}},
                required=["empowered_state_raw", "challenge"],
                handler=identify_empowered_state_handler,
                transition_callback=identify_empowered_state_callback
            )
        ]
    }

########################################################################
# Confirm Empowered State
########################################################################

async def confirm_empowered_state_handler(args: FlowArgs) -> FlowResult:
    return {"status": "success", "empowered_state_confirmed": True}

async def confirm_empowered_state_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    if result.get("empowered_state_confirmed"):
        await flow_manager.set_node("goodbye", create_goodbye_node())
    else:
        await flow_manager.set_node("identify_empowered_state", create_identify_empowered_state_node())

def create_confirm_empowered_state_node(emotions_summary: str, challenge: str)->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": f"Emotions Detected: {emotions_summary}. \
                Available Empowered States: {', '.join(CHALLENGE_TO_EMPOWERED_STATES[challenge])}. \
                Using his previous answer text and the emotions detected above pick the correct Empowered State. \
                Then confirm the emotions and the empowered state you selected with the user. Call confirm_empowered_state function after the user confirms your selection."}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="confirm_empowered_state",
                description="Record the user's confirmation of detected emotions",
                properties={"user_input": {"type": "string", "description": "User response confirming the emotions"}},
                required=["user_input"],
                handler=confirm_empowered_state_handler,
                transition_callback=confirm_empowered_state_callback
            )
        ]
    }

########################################################################
# Goodbye
########################################################################

def create_goodbye_node()->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": "Say goodbye using the user's name."}
        ],
        "functions": [],
        "post_actions" : [
            {
                "type": "end_conversation"
            }
        ]
    }





############## Unused nodes

########################################################################
# Consider Challenge
########################################################################

#waiting for user to say that they are ready
async def consider_challenge_handler(args: FlowArgs) -> FlowResult:
    user_ready = args.get("user_ready", "").lower()
    is_ready = any(word in user_ready for word in ["ready", "proceed", "continue", "yes", "yeah"])
    return {"status": "success", "user_ready": is_ready}

async def consider_challenge_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]consider_challenge_callback {result}")
    if result["user_ready"]:
        await flow_manager.set_node("select_challenge", create_select_challenge_node())
    else:
        await flow_manager.set_node("consider_challenge", create_consider_challenge_node())

def create_consider_challenge_node()->NodeConfig:
    return {
        "task_messages": [
            {"role": "system", "content": "Invite the user to consider difficult thought and a specific challenge associated with those thoughts which they have to match to a set of challenges printed on a poster in front of them, using language very similar to this prompt: \
            'Consider your thoughts... Is there one you wish you could avoid, one that calls for attention but makes you feel stuck, disconnected, or out of balance? Is there a current challenge you're facing that is associated with that thought?\
                Once you have done that, look at the challenges on the poster and let me know which one resonates with you. When you are ready to respond say you are ready or raise your hand to get the attention of a guide.'"}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="check_for_ready",
                description="Wait for the user to be ready to proceed",
                properties={"user_ready": {"type": "string", "description": "Is the user ready?"}},
                required=["user_ready"],
                handler=consider_challenge_handler,
                transition_callback=consider_challenge_callback
            )
        ],
        "ui_override": {
            "type": "button",
            "prompt": "Is participant ready?",
            "action_text": "I am ready"
        }
    }



########################################################################
# Wait for emotions
########################################################################

async def wait_for_emotions_handler(args: FlowArgs, flow_manager: FlowManager) -> FlowResult:
    # Wait until emotions have been processed
    logger.info("Waiting for emotions to be processed")
    #wait up to 60 seconds
    for _ in range(120):
        if flow_manager.state.get("emotions_fully_processed", False):
            break
        await asyncio.sleep(0.5)

    emotions_summary = flow_manager.state.get("emotions_summary", "")
    challenge = flow_manager.state.get("challenge", "")
    logger.info("Emotions processed, moving to confirm_emotions")
    return {"status": "success", "emotions_summary": emotions_summary, "challenge": challenge}

async def wait_for_emotions_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    if result["status"] == "success":
        await flow_manager.set_node("confirm_emotions", create_confirm_emotions_node(result["emotions_summary"], result["challenge"]))

def create_wait_for_emotions_node()->NodeConfig:
    return {
        "task_messages": [
            {"role": "system", "content": "Wait for emotions to be processed, once we have them we will ask for confirmation."}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="wait_for_emotions",
                description="Wait for emotions to be processed",
                properties={"emotions_summary": {"type": "string", "description": "The summary of emotions detected"}, "challenge": {"type": "string", "description": "The challenge detected"}},
                required=["emotions_summary", "challenge"],
                handler=wait_for_emotions_handler,
                transition_callback=wait_for_emotions_callback
            )
        ]
    }
