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
        "task": """Welcome the participant with a guided meditation, and wait for them to indicate readiness, then call the function check_for_ready. 
        
        IMPORTANT RULES:
        1. You have EXACTLY 2 attempts to understand if the participant is ready.
        2. After 2 failed attempts (where they don't clearly say they are ready), you MUST call the guide_greeting_assistance function.
        3. If the participant explicitly asks for help, call the guide_greeting_assistance function immediately.
        4. If the participant speaks about anything else, reply gently but keep returning to the task at hand.
        5. Until the participant indicates readiness with words like "ready", "yes", etc., do not proceed further.
        6. DO NOT make a third attempt - after 2 attempts, ALWAYS call for guide assistance.""",
        "suggested_language": "Welcome Seeker. To begin your quest, we invite you to ground and center with a few deep breaths. Know that you are safe here in your center. You're doing great! When you are ready to begin, please say 'I am ready'.",
    },
    "collect_name": {
        "task": "Ask the user for their name and record it with the collect_name function, then ask for confirmation with the confirm_name function. If the user does not share a name, gently keep returning to the task of getting their name. Do not go deeper into the conversation before moving on from this stage. If they dont share a name after 2 attempt, please call the guide_assistance function.",
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
           - You have EXACTLY 2 attempts to match their response to one of the available challenges. After 2 attempts, you MUST use the select_challenge function to direct them to look at the poster of challenges.
           - IMPORTANT: Do not make a third attempt at conversation. After 2 failed attempts, you MUST use the select_challenge function.""",
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
    },
}
   

async def greeting_ready_handler(args: FlowArgs, flow_manager: FlowManager) -> FlowResult:
    return {"status": "success", "user_ready": True}


async def greeting_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]greeting_callback: {result}")
    if result["status"] == "success" and result["user_ready"]:
        await flow_manager.set_node("collect_name", create_collect_name_node())
    else:
        await flow_manager.set_node("greeting", create_initial_node())


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
                    "user_ready": {"type": "boolean", "description": "User's response indicating readiness"}
                },
                required=["user_ready"],
                handler=greeting_ready_handler,
                transition_callback=greeting_callback
            ),
            FlowsFunctionSchema(
                name="guide_greeting_assistance",
                description="Call this when the user is not ready to proceed after 2 failed attempts or if the user indicates need for assistance.",
                properties={},
                required=[],
                handler=guide_greeting_assistance_handler,
                transition_callback=guide_greeting_assistance_callback
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

async def collect_name_handler(args: FlowArgs, flow_manager: FlowManager) -> FlowResult:
    user_name = args.get("user_name", "").strip()
    retry_count = flow_manager.state.get("name_retry_count", 0)
    
    # Basic validation - name should be at least 2 characters and not contain numbers
    if len(user_name) >= 2 and not any(c.isdigit() for c in user_name):
        flow_manager.state["name_retry_count"] = 0
        return {"status": "success", "user_name": user_name}
    elif retry_count < 1:
        # First retry
        flow_manager.state["name_retry_count"] = 1
        return {"status": "retry"}
    else:
        # Second failure - need guide assistance
        flow_manager.state["name_retry_count"] = 0  # Reset for next time
        return {"status": "guide_needed"}

async def collect_name_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]collect_name_callback: {result}")
    if result["status"] == "success":
        await flow_manager.set_node("collect_name", create_collect_name_node(
            f"Great! I heard your name is {result['user_name']}. Is that correct?"
        ))
    elif result["status"] == "retry":
        await flow_manager.set_node("collect_name", create_collect_name_node(
            "I didn't quite catch that. Could you please tell me your name again? Or would you prefer to be called Seeker?"
        ))
    else:
        await flow_manager.set_node("guide_assistance", create_name_guide_assistance_node())

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
        # Store the confirmed name in the flow state
        flow_manager.state["user_name"] = args.get("user_name", "Seeker")
        # Transition to the challenge identification stage
        await flow_manager.set_node("identify_challenge", create_identify_challenge_node())
    else:
        # If name is not confirmed, go back to name collection
        await flow_manager.set_node("collect_name", create_collect_name_node())

def create_collect_name_node(custom_prompt: str = None)->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": f"{custom_prompt or FLOW_STATES['collect_name']['task']}. IMPORTANT: Only call the name_guide_assistance function if: 1) The participant explicitly asks for help from a guide, or 2) You have made two attempts to collect their name and still cannot get a valid name."}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="collect_name",
                description="Collect the user's name",
                properties={
                    "user_name": {"type": "string", "description": "The user's name"},
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
            ),
            FlowsFunctionSchema(
                name="name_guide_assistance",
                description="Call this when the user is having trouble providing their name after 1 attempt or if they ask for help.",
                properties={},
                required=[],
                handler=call_name_guide_assistance,
                transition_callback=call_name_guide_assistance_callback
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
        # If the challenge is invalid, move to select_challenge stage
        await flow_manager.set_node("select_challenge", create_select_challenge_node())

async def move_to_select_challenge_handler(args: FlowArgs) -> FlowResult:
    return {"status": "success", "move_to_select": True}

async def move_to_select_challenge_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]move_to_select_challenge_callback {result}")
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
            ),
            FlowsFunctionSchema(
                name="move_to_select_challenge",
                description="Call this when you cannot determine the challenge after 2 attempts. This will move to the select_challenge stage where the user can choose from the poster.",
                properties={},
                required=[],
                handler=move_to_select_challenge_handler,
                transition_callback=move_to_select_challenge_callback
            )
        ]
    }

########################################################################
# Select Challenge
########################################################################

async def select_challenge_handler(args: FlowArgs) -> FlowResult:
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
        await flow_manager.set_node("guide_assistance", create_challenge_guide_assistance_node())

def create_select_challenge_node()->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": f"""Follow this process in order:
You couldnt determine the challenge from the conversation, so direct them to look at the poster of challenges and ask them to tell you which one resonates with them.
If they they still have trouble selecting a challenge from the list of challenges (you dont need to name them) after looking at the poster, call the challenge_guide_assistance function.


Available Challenges: {', '.join(FLOW_STATES['select_challenge']['options'])}"""}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="select_challenge",
                description=f"Record the user's selected challenge, match the user challenge with one of the following options: {', '.join(FLOW_STATES['select_challenge']['options'])}",
                properties={"challenge": {"type": "string", "description": "The user's selected challenge"}},
                required=["challenge"],
                handler=select_challenge_handler,
                transition_callback=select_challenge_callback
            ),
            FlowsFunctionSchema(
                name="challenge_guide_assistance",
                description="Call this only if the user has trouble selecting a challenge even after looking at the poster.",
                properties={},
                required=[],
                handler=call_challenge_guide_assistance,
                transition_callback=call_challenge_guide_assistance_callback
            )
        ],
        "ui_override": {
            "type": "list",
            "prompt": "Which challenge listed is most alive for you right now?",
            "options": FLOW_STATES["select_challenge"]["options"]
        }
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
        await flow_manager.set_node("identify_empowered_state", create_identify_empowered_state_node(flow_manager))
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
            {"role": "system", "content": f"""IMPORTANT: This is ONLY a simple confirmation step. 

Task: Ask the user to confirm if '{challenge}' is their challenge and if the emotions detected ({emotions_summary}) resonate with them. Use phrasing similar to:
"It sounds like you are dealing with {challenge} and it makes you feel {emotions_summary}. Is that correct?"

Do NOT explore these emotions or the challenge further.
Do NOT ask additional follow-up questions about how these manifest.
ONLY ask for confirmation and wait for their yes/no response."""}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="confirm_challenge",
                description="Call this after the user confirms the challenge and emotions, without further exploration.",
                properties={},
                required=[],
                handler=confirm_challenge_handler,
                transition_callback=confirm_challenge_callback
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
    logger.info(f"[Flow]identify_empowered_state_handler: {empowered_state_raw}")
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
        await flow_manager.set_node("identify_empowered_state", create_identify_empowered_state_node(flow_manager))

def create_identify_empowered_state_node(flow_manager: FlowManager=None)->NodeConfig:
    challenge = ""
    if flow_manager:
        challenge = flow_manager.state.get('challenge', '')
    
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": f"""Follow this process in order:
1. First, ask the participant about their desired empowered state and try to understand it through conversation. You have EXACTLY 2 attempts to match their response to one of the available empowered states. After 2 attempts, you MUST move to step 2.
2. If after 2 attempts you still cannot match their response to an empowered state, direct them to look at the poster of empowered states and ask them to tell you which one resonates with them.
3. Only if they still have trouble selecting an empowered state after looking at the poster, call the empowered_state_guide_assistance function.

IMPORTANT: 
- You MUST move to step 2 after exactly 2 attempts, regardless of the participant's response.
- Do not make a third attempt at conversation.
- If the participant's response doesn't match any empowered state after 2 attempts, move to the poster stage.

Available Empowered States for your challenge: {', '.join(CHALLENGE_TO_EMPOWERED_STATES[challenge] if challenge else ["None specified"])}"""}
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
            ),
            FlowsFunctionSchema(
                name="empowered_state_guide_assistance",
                description="Call this only if the user has trouble selecting an empowered state even after looking at the poster.",
                properties={},
                required=[],
                handler=call_empowered_state_guide_assistance,
                transition_callback=call_empowered_state_guide_assistance_callback
            )
        ]
    }

########################################################################
# Confirm Empowered State
########################################################################

async def confirm_empowered_state_handler(args: FlowArgs, flow_manager: FlowManager) -> FlowResult:
    empowered_state = args.get("empowered_state", "").lower()
    logger.info(f"[Flow]confirm_empowered_state_handler: {empowered_state}")
    flow_manager.state["empowered_state"] = empowered_state
    return {"status": "success", "empowered_state_confirmed": True, "empowered_state": empowered_state}

async def confirm_empowered_state_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    if result.get("empowered_state_confirmed"):
        await flow_manager.set_node("goodbye", create_goodbye_node())
    else:
        await flow_manager.set_node("identify_empowered_state", create_identify_empowered_state_node(flow_manager))

def create_confirm_empowered_state_node(emotions_summary: str, challenge: str)->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": f"Emotions Detected: {emotions_summary}. \
                Available Empowered States: {', '.join(CHALLENGE_TO_EMPOWERED_STATES[challenge])}. \
                Using the user's previous answer text and the emotions detected above pick the correct Empowered State from the list of available Empowered States for the selected challenge {challenge}. \
                Then confirm the emotions and the empowered state you selected with the user. For example: 'It sounds like you will feel {emotions_summary} as you move toward <say empowered state here>. Is that correct?'"}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="confirm_empowered_state",
                description="Record the user's confirmation of the empowered state and emotions",
                properties={"user_input": {
                    "type": "string", 
                    "description": "User response confirming the empowered state and emotions"},
                    "empowered_state": {
                        "type": "string", 
                        "description": "Empowered state selected by the user"}
                },
                required=["user_input", "empowered_state"],
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



########################################################################
# Guide Assistance
########################################################################



async def call_greeting_guide_assistance(args: FlowArgs) -> FlowResult:
    # Import at function level to avoid circular imports
    from status_utils import status_updater
    logger.info(f"[DEBUG] call_greeting_guide_assistance called with args: {args}")
    
    try:
        logger.info(f"[DEBUG] About to call status_updater.needs_help('Greeting', True)")
        await status_updater.needs_help("Greeting", True)
        logger.info(f"[DEBUG] Successfully called status_updater.needs_help")
    except Exception as e:
        import traceback
        logger.error(f"[DEBUG] Error in call_greeting_guide_assistance: {e}")
        logger.error(f"[DEBUG] Traceback: {traceback.format_exc()}")
    
    return {"status": "success", "call_guide_assistance": True}

async def call_greeting_guide_assistance_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]call_guide_assistance_callback: {result}")
    if result["status"] == "success":
        await flow_manager.set_node("guide_assistance", create_greeting_guide_assistance_node())

async def call_name_guide_assistance(args: FlowArgs) -> FlowResult:
    # Import at function level to avoid circular imports
    from status_utils import status_updater
    logger.info(f"[DEBUG] call_name_guide_assistance called with args: {args}")
    
    try:
        logger.info(f"[DEBUG] About to call status_updater.needs_help('Name collection', True)")
        await status_updater.needs_help("Name collection", True)
        logger.info(f"[DEBUG] Successfully called status_updater.needs_help")
    except Exception as e:
        import traceback
        logger.error(f"[DEBUG] Error in call_name_guide_assistance: {e}")
        logger.error(f"[DEBUG] Traceback: {traceback.format_exc()}")
    
    return {"status": "success", "call_guide_assistance": True}

async def call_name_guide_assistance_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]call_name_guide_assistance_callback: {result}")
    if result["status"] == "success":
        await flow_manager.set_node("name_guide_assistance", create_name_guide_assistance_node())

async def call_challenge_guide_assistance(args: FlowArgs) -> FlowResult:
    # Import at function level to avoid circular imports
    from status_utils import status_updater
    logger.info(f"[DEBUG] call_challenge_guide_assistance called with args: {args}")
    
    try:
        logger.info(f"[DEBUG] About to call status_updater.needs_help('Challenge selection', True)")
        await status_updater.needs_help("Challenge selection", True)
        logger.info(f"[DEBUG] Successfully called status_updater.needs_help")
    except Exception as e:
        import traceback
        logger.error(f"[DEBUG] Error in call_challenge_guide_assistance: {e}")
        logger.error(f"[DEBUG] Traceback: {traceback.format_exc()}")
    
    return {"status": "success", "call_guide_assistance": True}

async def call_challenge_guide_assistance_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]call_challenge_guide_assistance_callback: {result}")
    if result["status"] == "success":
        await flow_manager.set_node("challenge_guide_assistance", create_challenge_guide_assistance_node())

async def call_empowered_state_guide_assistance(args: FlowArgs) -> FlowResult:
    # Import at function level to avoid circular imports
    from status_utils import status_updater
    logger.info(f"[DEBUG] call_empowered_state_guide_assistance called with args: {args}")
    
    try:
        logger.info(f"[DEBUG] About to call status_updater.needs_help('Empowered state selection', True)")
        await status_updater.needs_help("Empowered state selection", True)
        logger.info(f"[DEBUG] Successfully called status_updater.needs_help")
    except Exception as e:
        import traceback
        logger.error(f"[DEBUG] Error in call_empowered_state_guide_assistance: {e}")
        logger.error(f"[DEBUG] Traceback: {traceback.format_exc()}")
    
    return {"status": "success", "call_guide_assistance": True}

async def call_empowered_state_guide_assistance_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]call_empowered_state_guide_assistance_callback: {result}")
    if result["status"] == "success":
        await flow_manager.set_node("empowered_state_guide_assistance", create_empowered_state_guide_assistance_node())

async def guide_greeting_assistance_handler(args: FlowArgs) -> FlowResult:
    logger.info(f"[Flow]guide_greeting_assistance_handler called")
    
    # Import status_updater here to avoid circular imports
    from status_utils import status_updater
    
    try:
        logger.info(f"[DEBUG] About to call status_updater.needs_help('Greeting', True) from guide_greeting_assistance_handler")
        # This is the actual call that sends the help request to Resolume
        await status_updater.needs_help("Greeting", True)
        logger.info(f"[DEBUG] Successfully called status_updater.needs_help from guide_greeting_assistance_handler")
    except Exception as e:
        import traceback
        logger.error(f"[DEBUG] Error in guide_greeting_assistance_handler: {e}")
        logger.error(f"[DEBUG] Traceback: {traceback.format_exc()}")
    
    return {"status": "success", "call_guide_assistance": True}

async def guide_greeting_assistance_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]guide_greeting_assistance_callback called with result: {result}")
    # Always transition to guide assistance node regardless of result
    await flow_manager.set_node("guide_assistance", create_greeting_guide_assistance_node())

def create_greeting_guide_assistance_node()->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": """I am having trouble understanding if you're ready to begin. Please raise your hand and a guide will help you.
IMPORTANT: While waiting for the guide, you can still let me know if you're ready by saying 'I am ready'."""}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="check_for_ready",
                description="Call this when the user is ready to proceed.",
                properties={
                    "user_ready": {"type": "string", "description": "User's response indicating readiness"}
                },
                required=["user_ready"],
                handler=greeting_ready_handler,
                transition_callback=greeting_callback
            ),
            FlowsFunctionSchema(
                name="guide_response",
                description="Record the guide's response about participant readiness",
                properties={"is_ready": {"type": "boolean", "description": "Whether the participant is ready to begin"}},
                required=["is_ready"],
                handler=greeting_guide_response_handler,
                transition_callback=greeting_guide_response_callback
            )
        ],
        "ui_override": {
            "type": "list",
            "prompt": "Guide: Is participant ready?",
            "options": ["Yes", "No"]
        }
    }

def create_name_guide_assistance_node()->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": """I am having trouble understanding your name. Please raise your hand and a guide will help you enter your name.
IMPORTANT: While waiting for the guide, you can still tell me your name directly."""}
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
                name="guide_response",
                description="Record the guide's input of the participant's name",
                properties={"user_name": {"type": "string", "description": "The participant's name"}},
                required=["user_name"],
                handler=name_guide_response_handler,
                transition_callback=name_guide_response_callback
            )
        ],
        "ui_override": {
            "type": "list",
            "prompt": "Guide: Enter the participant's name",
            "options": ["Seeker"]  # Default option
        }
    }
    
def create_challenge_guide_assistance_node()->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": f"""I am having trouble understanding which challenge resonates with you. Please raise your hand and a guide will help you select the most appropriate challenge state.
IMPORTANT: While waiting for the guide, you can still tell me which challenge resonates with you by looking at the poster and telling me directly.

Available Challenges: {', '.join(FLOW_STATES['select_challenge']['options'])}"""}
        ],
        "functions": [
            FlowsFunctionSchema(
                name="select_challenge",
                description="Record the user's selected challenge",
                properties={"challenge": {"type": "string", "description": "The user's selected challenge"}},
                required=["challenge"],
                handler=select_challenge_handler,
                transition_callback=select_challenge_callback
            ),
            FlowsFunctionSchema(
                name="guide_response",
                description="Record the guide's selection of the participant's challenge",
                properties={"challenge": {"type": "string", "description": "The selected challenge"}},
                required=["challenge"],
                handler=challenge_guide_response_handler,
                transition_callback=challenge_guide_response_callback
            )
        ],
        "ui_override": {
            "type": "list",
            "prompt": "Guide: Select the most appropriate challenge state",
            "options": FLOW_STATES["select_challenge"]["options"]
        }
    }

def create_empowered_state_guide_assistance_node()->NodeConfig:
    return {
        "role_messages": [
            {"role": "system", "content": SYSTEM_ROLE},
        ],
        "task_messages": [
            {"role": "system", "content": f"""I am having trouble understanding your desired empowered state. Please raise your hand and a guide will help you identify the most appropriate empowered state.
IMPORTANT: While waiting for the guide, you can still tell me which empowered state resonates with you by looking at the poster and telling me directly.

Available Empowered States for your challenge: {', '.join(CHALLENGE_TO_EMPOWERED_STATES[flow_manager.state.get('challenge', '')])}"""}
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
            ),
            FlowsFunctionSchema(
                name="guide_response",
                description="Record the guide's selection of the participant's empowered state",
                properties={"empowered_state": {"type": "string", "description": "The selected empowered state"}},
                required=["empowered_state"],
                handler=empowered_state_guide_response_handler,
                transition_callback=empowered_state_guide_response_callback
            )
        ],
        "ui_override": {
            "type": "list",
            "prompt": "Guide: Select the most appropriate empowered state",
            "options": CHALLENGE_TO_EMPOWERED_STATES[flow_manager.state.get("challenge", "")]
        }
    }

async def greeting_guide_response_handler(args: FlowArgs) -> FlowResult:
    is_ready = args.get("is_ready", False)
    # Import at function level to avoid circular imports
    from status_utils import status_updater
    logger.info(f"[DEBUG] greeting_guide_response_handler called with args: {args}")
    
    try:
        logger.info(f"[DEBUG] About to call status_updater.needs_help('Greeting', False)")
        # Turn off help request since guide has responded
        await status_updater.needs_help("Greeting", False)
        logger.info(f"[DEBUG] Successfully turned off help request")
    except Exception as e:
        import traceback
        logger.error(f"[DEBUG] Error in greeting_guide_response_handler: {e}")
        logger.error(f"[DEBUG] Traceback: {traceback.format_exc()}")
    
    return {"status": "success", "is_ready": is_ready}

async def greeting_guide_response_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]greeting_guide_response_callback: {result}")
    if result["is_ready"]:
        await flow_manager.set_node("collect_name", create_collect_name_node())
    else:
        await flow_manager.set_node("greeting", create_initial_node())

async def name_guide_response_handler(args: FlowArgs) -> FlowResult:
    user_name = args.get("user_name", "").strip()
    # Turn off help request since guide has responded
    await status_updater.needs_help("Name collection", False)
    return {"status": "success", "user_name": user_name}

async def name_guide_response_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]name_guide_response_callback: {result}")
    await flow_manager.set_node("collect_name", create_collect_name_node(
        f"Great! I heard your name is {result['user_name']}. Is that correct?"
    ))

async def challenge_guide_response_handler(args: FlowArgs) -> FlowResult:
    challenge = args.get("challenge", "").lower()
    # Turn off help request since guide has responded
    await status_updater.needs_help("Challenge selection", False)
    return {"status": "success", "challenge": challenge}

async def challenge_guide_response_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]challenge_guide_response_callback: {result}")
    await flow_manager.set_node("confirm_challenge", create_confirm_challenge_node(flow_manager))

async def empowered_state_guide_response_handler(args: FlowArgs) -> FlowResult:
    empowered_state = args.get("empowered_state", "").lower()
    # Turn off help request since guide has responded
    await status_updater.needs_help("Empowered state selection", False)
    return {"status": "success", "empowered_state": empowered_state}

async def empowered_state_guide_response_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]empowered_state_guide_response_callback: {result}")
    await flow_manager.set_node("confirm_empowered_state", create_confirm_empowered_state_node(
        emotions_summary=flow_manager.state.get("emotions_summary", ""),
        challenge=flow_manager.state.get("challenge", "")
    ))



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
