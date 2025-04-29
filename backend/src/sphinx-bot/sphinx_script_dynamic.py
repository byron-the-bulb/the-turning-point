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
    2. Do not repeat yourself, dont be too succint but dont be verbose either.
    3. Insert a <break time="500ms"/> tag between sentences (after periods, exclamation points, or question marks followed by a space).
    4. Ensure sentences are properly punctuated to mark sentence boundaries.
    5. Do not use SSML tags other than <break> unless explicitly requested.
    6. Produce natural, conversational text with clear sentence breaks.
    7. Use two question marks to emphasize questions. For example, "Are you here??" vs. "Are you here?"
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
        "task": "Welcome the participant with a guided meditation, and wait for them to indicate readiness. When the user indicates readiness, call the check_for_ready function. If the user speaks about anything else, reply gently and curiously byt keep returning to the task at hand. Untill the user indicates that they are ready you should not delve further into the conversation.",
        "suggested_language": "Welcome Seeker. To begin your quest, we invite you to ground and center with a few deep breaths. Know that you are safe here in your center. You're doing great! When you are ready to begin, please say 'I am ready'.",
    },
    "collect_name": {
        "task": "Ask the user for their name and record it with the collect_name function, then ask for confirmation with the confirm_name function. If the user does not share a name, gently keep returning to the task of getting their name or ask if you can call them Seeker. Do not go deeper into the conversation before moving on from this stage",
        "suggested_language": "Before we get started, please tell me your name?",
    },
    "identify_challenge": {
        "task": """Available Challenges: Fearful, Anxious, Stagnant, Ruminating, Disassociated, Numb, Unhealthy, Scarcity, Excluded, Lack of Control, Lack of Agency, Disembodied, Ungrounded, Obsessed, Silenced, Unheard, Lack of Purpose, Unmotivated, Shameful.
        Prompt the participant to speak about what they find challenging at the moment,
        evaluate their input and pick one of the the challenge states listed above that matches the participant state.
        Analyze their response as a therapist would:
           - Look for themes, emotions, and qualities they're describing
           - Match their described qualities to one of the available challenge states
           - Use the identify_challenge function to evaluate your pick
           - If the participant doesn't mention any of the challenges, pick the most relevant one based on the conversation
           - Only try once to identify the challenge, if you fail to do so using the identify_challenge function, move on to the next step""",
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
        ]
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
    user_ready = args.get("user_ready", "").lower()
    retry_count = args.get("retry_count", 0)
    
    is_ready = any(word in user_ready for word in ["ready", "proceed", "continue", "yes", "yeah"])
    if is_ready:
        return {"status": "success", "retry_count": 0}
    elif retry_count < 1:
        # First retry
        return {"status": "retry", "retry_count": 1}
    else:
        # Second failure - need guide assistance
        return {"status": "guide_needed", "retry_count": 2}

async def greeting_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]greeting_callback: {result}")
    if result["status"] == "success":
        await flow_manager.set_node("collect_name", create_collect_name_node())
    elif result["status"] == "retry":
        # More lenient prompt for retry
        await flow_manager.set_node("greeting", create_greeting_node(
            "I didn't quite catch that. Could you please let me know when you're ready to begin? You can say 'I am ready' or just 'ready'."
        ))
    else:
        # Guide assistance needed
        await flow_manager.set_node("guide_assistance", create_guide_assistance_node(
            "The participant seems to be having trouble indicating readiness. Please check if they are ready to begin."
        ))

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
                properties={
                    "user_ready": {"type": "string", "description": "User's response indicating readiness"},
                    "retry_count": {"type": "integer", "description": "Number of retries attempted"}
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


########################################################################
# Collect Name
########################################################################

async def collect_name_handler(args: FlowArgs) -> FlowResult:
    user_name = args.get("user_name", "").strip()
    # Check if we're on a retry
    retry_count = args.get("retry_count", 0)
    
    # Basic validation - name should be at least 2 characters and not contain numbers
    if len(user_name) >= 2 and not any(c.isdigit() for c in user_name):
        return {"status": "success", "user_name": user_name, "retry_count": 0}
    elif retry_count < 1:
        # First retry
        return {"status": "retry", "retry_count": 1}
    else:
        # Second failure - need guide assistance
        return {"status": "guide_needed", "retry_count": 2}

async def collect_name_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]collect_name_callback: {result}")
    if result["status"] == "success":
        await flow_manager.set_node("confirm_name", create_collect_name_node(
            f"Great! I heard your name is {result['user_name']}. Is that correct?"
        ))
    elif result["status"] == "retry":
        await flow_manager.set_node("collect_name", create_collect_name_node(
            "I didn't quite catch that. Could you please tell me your name again?"
        ))
    else:
        await flow_manager.set_node("guide_assistance", create_guide_assistance_node(
            "The participant seems to be having trouble providing their name. Please help them enter their name."
        ))

async def confirm_name_handler(args : FlowArgs) -> FlowResult:
    confirmed = args["confirmed"]
    return {"status": "success", "confirmed": confirmed}

async def confirm_name_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]confirm_name_callback: {result}")
    if result["confirmed"]:
        await flow_manager.set_node("identify_challenge", create_identify_challenge_node())
    else:
        await flow_manager.set_node("collect_name", create_collect_name_node())

def create_collect_name_node(custom_prompt: str = None)->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": custom_prompt or FLOW_STATES["collect_name"]["task"]}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="collect_name",
                description="Collect the user's name",
                properties={
                    "user_name": {"type": "string", "description": "The user's name"},
                    "retry_count": {"type": "integer", "description": "Number of retries attempted"}
                },
                required=["user_name"],
                handler=collect_name_handler,
                transition_callback=collect_name_callback
            ),
            FlowsFunctionSchema(
                name="confirm_name",
                description="Confirm if the saved name is correct.",
                properties={"confirmed": {"type": "boolean"}},
                required=["confirmed"],
                handler=confirm_name_handler,
                transition_callback=confirm_name_callback
            )
        ],
        "ui_override": {
            "type": "text_input",
            "prompt": "Enter your name",
            "placeholder": "Type your name here"
        }
    }

########################################################################
# Identify Challenge
########################################################################
async def identify_challenge_handler(args: FlowArgs) -> FlowResult:
    challenge = args.get("challenge", "").lower()
    logger.info(f"[Flow]identify_challenge_handler: {challenge}")
    #Validate challenge by checking if challenge contains one of the following words
    options = [word.lower() for word in FLOW_STATES["identify_challenge"]["options"]]
    if not any(word in challenge for word in options):
        return {"status": "error", "message": "Invalid challenge"}
    return {"status": "success", "challenge": challenge}

async def identify_challenge_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]identify_challenge_callback {result}")
    if result["status"] == "success":
        await flow_manager.set_node("confirm_challenge", create_confirm_challenge_node(flow_manager))
    else:
        await flow_manager.set_node("select_challenge", create_select_challenge_node())

def create_identify_challenge_node()->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": FLOW_STATES["identify_challenge"]["task"]}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="identify_challenge",
                description="Identify the challenge the user is facing",
                properties={"challenge": {"type": "string", "description": "The challenge the user is facing"}},
                required=["challenge"],
                handler=identify_challenge_handler,
                transition_callback=identify_challenge_callback
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
        await flow_manager.set_node("confirm_challenge", create_confirm_challenge_node(flow_manager))
    else:
        await flow_manager.set_node("guide_assistance", create_guide_assistance_node())

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
                description="Record the user's selected challenge",
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
        await flow_manager.set_node("identify_empowered_state", create_identify_empowered_state_node())
    else:
        await flow_manager.set_node("select_challenge", create_select_challenge_node())

def create_confirm_challenge_node(flow_manager: FlowManager) -> NodeConfig:
    emotions_summary = flow_manager.state.get("emotions_summary", "")
    challenge = flow_manager.state.get("challenge", "")
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": f"It sounds like you are dealing with {challenge} and it makes you feel {emotions_summary}. Is that correct?"}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="confirm_challenge",
                description="Call this after the user confirms the challenge and emotions.",
                properties={},
                required=[],
                handler=confirm_challenge_handler,
                transition_callback=confirm_challenge_callback,
            )
        ],
        "ui_override": {
            "type": "list",
            "prompt": "Is this accurate?",
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
        await flow_manager.set_node("confirm_empowered_state", create_confirm_empowered_state_node(
            emotions_summary=emotions_summary,
            challenge=challenge
            ))
    else:
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
                Then confirm the emotions and the empowered state you selected with the user. For example: 'It sounds like you will feel {emotions_summary} as you move toward {empowered_state}. Is that correct?'"}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="confirm_empowered_state",
                description="Record the user's confirmation of the empowered state and emotions",
                properties={"user_input": {"type": "string", "description": "User response confirming the empowered state and emotions"}},
                required=["user_input"],
                handler=confirm_empowered_state_handler,
                transition_callback=confirm_empowered_state_callback
            )
        ],
        "ui_override": {
            "type": "list",
            "prompt": "Is this accurate?",
            "options": ["Yes", "No"]
        }
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

async def guide_assistance_handler(args: FlowArgs) -> FlowResult:
    challenge = args.get("challenge", "").lower()
    logger.info(f"[Flow]guide_assistance_handler: {challenge}")
    return {"status": "success", "challenge": challenge}

async def guide_assistance_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]guide_assistance_callback {result}")
    if result["status"] == "success":
        await flow_manager.set_node("confirm_challenge", create_confirm_challenge_node(flow_manager))
    else:
        await flow_manager.set_node("guide_assistance", create_guide_assistance_node())
    
def create_guide_assistance_node()->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": "Please raise your hand to get the attention of a guide. They will help you select the most appropriate challenge state from the options available."}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="guide_assistance",
                description="Wait for guide to select challenge",
                properties={"challenge": {"type": "string", "description": "The challenge selected by the guide"}},
                required=["challenge"],
                handler=guide_assistance_handler,
                transition_callback=guide_assistance_callback
            )
        ],
        "ui_override": {
            "type": "list",
            "prompt": "Guide: Select the most appropriate challenge state",
            "options": FLOW_STATES["select_challenge"]["options"]
        }
    }
