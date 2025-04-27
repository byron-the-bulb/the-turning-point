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
    1. Your responses will be converted to audio, avoid special characters or text formatting that is not translatable
    2. NEVER generate or simulate user inputs
    3. ONLY evaluate real user inputs that are provided to you
    4. Never deviate from the task at hand or generate simulated responses"""

FLOW_STATES = {
    "greeting": {
        "task": "Welcome the participant with a guided meditation, and wait for them to indicate readiness. When the user indicates readiness, call the check_for_ready function.",
        "suggested_language": "Welcome Seeker. To begin your quest, we invite you to ground and center with a few deep breaths: Inhale-3-4-5, Exhale-3-4-5, Inhale-3-4-5, exhale-3-4-5, inhale-3-4-5, exhale-3-4-5. Know that you are safe here in your center. You're doing great! When you are ready to begin, please say 'I am ready'.",
    },
    "collect_name": {
        "task": "Ask the user for their name and record it with the collect_name function, then ask for confirmation with the confirm_name function.",
        "suggested_language": "Before we get started, please tell me your name?",
    },
    "identify_challenge": {
        "task": "Help the participant identify their current challenging state by picking from the list of options presented to them in a poster, then ask for confirmation. Use the select_challenge fuction to record the user challenge, after the user confirms the challenge call the confirm_challenge function.",
        "options": [
            "Fearful","Anxious",
            "Stagnant","Ruminating",
            "Disassociated","Numb",
            "Unhealthy",
            "Scarcity",
            "Excluded",
            "Lack of Control/Agency",
            "Disembodied","Ungrounded",
            "Obsessed",
            "Silenced","Unheard",
            "Lack of Purpose","Unmotivated",
            "Shameful"
        ],
        "suggested_language": "Consider your thoughts. Is there one you wish you could avoid, one that calls for attention but makes you feel stuck, disconnected, or out of balance? What wisdom can be found if you hold that thought with love and care for all of who you are, from your heart center? Is there a current challenge you're facing that is associated with that thought? Which of these challenging states listed on this poster resonate with you at this moment?",
    },
    "explore_challenge" : {
        "task" : "Guide the user in exploring their challenge in depth. Example : 'I see you're feeling fearful. What is it like to be going through it?'. Record the user input giving them ample time to respond and for the sphinx system to process their emotions."
    },
    "identify_empowered_state": {
        "task": "Guide the participant in envisioning their desired future state",
        "options": None,  # We'll get these dynamically based on the challenge
        "suggested_language": "What if your challenges are just the beginning of a quest? What treasures will you gain along the way? Envisioning what you seek will help you find your path. When you have passed through this challenge, what will you be like? How will you feel? How will you live your life on the other side of this experience?",
        "confirmation_prompt": "It sounds like you will feel {empowered_state} and experience {empowered_emotions}. Is this correct?",
        "retry_prompt": "I didn't quite catch that. Could you please describe your envisioned state again?",
        "denial_prompt": "I apologize for misunderstanding. Could you please describe your envisioned state again?",
        "next_state": "goodbye",
        "evaluation_instructions": """When evaluating the user's input:
        1. If the user describes their envisioned state, analyze their response as a therapist would:
           - Look for themes, emotions, and qualities they're describing
           - Consider how their vision represents growth from their current challenge
           - Match their described qualities to one of the available empowered states
           
           - For the current challenge state "{challenge}", the available empowered states are: [OPTIONS]
           
           - If you can identify a match from the options list, return:
             {{"status": "success", "result": "matched_state", "needs_confirmation": true}}
        
        2. If the input is a confirmation (e.g., 'Yes', 'That's correct', 'Yes that's correct', 'Yes that's great', 'Correct', 'That's right'), return:
           {{"status": "success", "result": "previously_stored_state", "needs_confirmation": false}}
        
        3. If the input is a denial (e.g., 'No', 'That's not right', 'That's not correct'), return:
           {{"status": "incomplete", "needs_more_info": true}}
        
        4. For any other input, return:
           {{"status": "incomplete", "needs_more_info": true}}
        
        IMPORTANT: 
        - Act as a therapist interpreting the user's vision
        - Look for underlying themes and qualities in their response
        - Consider how their vision represents growth from their current challenge
        - Match their described qualities to the available empowered states
        - The result field MUST contain the exact state from the options list
        - Never return needs_more_info for a confirmation
        - The options available depend on the current challenge state
        - If the user mentions a state that matches any of these options, even partially, return that exact option
        - For example, if the user says 'I want to trust others' and 'Trusting Others' is in the options list, return 'Trusting Others' as the result
        - When the user selects a state, you MUST set needs_confirmation to true to move to the confirmation phase
        - The confirmation phase is crucial - it allows the user to confirm their selection before moving forward
        - If the user has selected a state, you MUST move to confirmation by setting needs_confirmation to true
        """
    },
    "goodbye": {
        "task": "Conclude the session and prepare for video experience",
        "options": None,
        "suggested_language": "Thank you for sharing and taking the time to explore your inner landscape! Now please let your guide know you are ready to view your destiny.",
        "confirmation_prompt": None,
        "retry_prompt": None,
        "denial_prompt": None,
        "next_state": None,
        "evaluation_instructions": """When evaluating the user's input:
        1. If the input indicates readiness (e.g., 'I am ready', 'Yes, I'm ready', 'Let's do it'), return:
           {{"status": "success", "result": "ready", "needs_confirmation": false}}
        
        2. For any other input, return:
           {{"status": "incomplete", "needs_more_info": true}}
        
        IMPORTANT: 
        - The task is complete when the user indicates they are ready
        - No confirmation is needed for this state"""
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
            {"role": "system", "content": f"{FLOW_STATES["greeting"]["task"]}. Suggested language: {FLOW_STATES["greeting"]["suggested_language"]}"},
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
    # This will be sent back to the client in a TranscriptionFrame
    return {"status": "success", "user_name": user_name}

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
        await flow_manager.set_node("select_challenge", create_select_challenge_node())
    else:
        await flow_manager.set_node("collect_name", create_collect_name_node())

def create_collect_name_node()->NodeConfig:
    return {
        "task_messages": [
            {"role": "system", "content": ""},
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
    if not any(word in challenge for word in FLOW_STATES["select_challenge"]["options"]):
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

async def confirm_challenge_handler(args : FlowArgs) -> FlowResult:
    return {"status": "success"}

async def confirm_challenge_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]confirm_challenge_callback {result}")
    if result["status"] == "success":
        await flow_manager.set_node("record_challenge_in_depth", create_record_challenge_in_depth_node())
    else:
        await flow_manager.set_node("select_challenge", create_select_challenge_node())

def create_select_challenge_node()->NodeConfig:
    return {
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
            ),
            FlowsFunctionSchema(
                    name="confirm_challenge",
                    description="Call this when the user confirms the challenge",
                    properties={},
                    required=[],
                    handler=confirm_challenge_handler,
                    transition_callback=confirm_challenge_callback,
            )
        ],
        "ui_override": {
            "type": "list",
            "prompt": "Which challenge listed is most alive for you right now?",
            "options": FLOW_STATES["select_challenge"]["options"]
        },
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
        await flow_manager.set_node("challenge_in_depth", create_record_challenge_in_depth_node())


def create_record_challenge_in_depth_node()->NodeConfig:
    return {
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
        await flow_manager.set_node("goodbye", create_goodbye_node())
    else:
        await flow_manager.set_node("challenge_in_depth", create_record_challenge_in_depth_node())


def create_confirm_emotions_node(emotions_summary: str, challenge: str)->NodeConfig:
    return {
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
# Goodbye
########################################################################

def create_goodbye_node()->NodeConfig:
    return {
        "task_messages": [
            {"role": "system", "content": "Say goodbye using the user's name."}
        ],
        "functions": []
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
# Confirm Challenge
########################################################################
    
async def confirm_challenge_handler(args : FlowArgs) -> FlowResult:
    user_input = args.get("user_input", "").lower()
    logger.info(f"[Flow]confirm_challenge_handler {user_input}")
    is_confirming = any(word in user_input for word in ["ready", "proceed", "continue", "yes"])
    
    return {"status": "success", "user_confirming": is_confirming}

async def confirm_challenge_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]confirm_challenge_callback {result}")
    if result["user_confirming"]:
        await flow_manager.set_node("record_challenge_in_depth", create_record_challenge_in_depth_node())
    else:
        await flow_manager.set_node("select_challenge", create_select_challenge_node())

def create_confirm_challenge_node()->NodeConfig:
    return {
        "task_messages": [
            {"role": "system", "content": "Confirm with the user the previously selected challenge. Example : 'You have selected Fearful. Is this correct?'"}
        ],
        "functions": [
            FlowsFunctionSchema(
                    name="confirm_challenge",
                    description="Record the user's confirmation that we have selected the correct challenge, yes or no, positive or negative, or a word of affirmation or denial",
                    properties={"user_input": {"type": "string", "description": "The user's confirmation, yes or no, positive or negative, or a word of affirmation or denial"}},
                    required=["user_input"],
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
