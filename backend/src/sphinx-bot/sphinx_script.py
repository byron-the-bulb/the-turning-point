from pipecat_flows import FlowManager, FlowConfig, FlowsFunctionSchema, FlowArgs, FlowResult
from status_utils import status_updater
from loguru import logger

# Define handler functions
# async def collect_name_handler(args, result, flow_manager):
#     name = result.get("name")
#     flow_manager.state["name"] = name
#     await flow_manager.set_node("goodbye_node", create_summary_node())

async def collect_name_handler(args : FlowArgs) -> FlowResult:
    name = args["name"]
    # This will be sent back to the client in a TranscriptionFrame
    return {"status": "success", "name": name}

async def ready_handler(args: FlowArgs) -> FlowResult:
    logger.info(f"[Flow]ready_handler: {args}")

    user_input = args.get("user_input", "").lower()
    is_ready = any(word in user_input for word in ["ready", "proceed", "continue", "yes"])
    return {"status": "success", "user_ready": is_ready}

async def greeting_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]greeting_callback: {result}")
    if result["user_ready"]:
        await flow_manager.set_node("collect_name", sphinx_flow_config["nodes"]["collect_name"])
    else:
        await flow_manager.set_node("greeting", sphinx_flow_config["nodes"]["greeting"])

async def consider_challenge_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]consider_challenge_callback: {result}")
    if result["user_ready"]:
        await flow_manager.set_node("select_challenge", sphinx_flow_config["nodes"]["select_challenge"])
    else:
        await flow_manager.set_node("guided_meditation", sphinx_flow_config["nodes"]["guided_meditation"])

async def select_challenge_handler(args : FlowArgs) -> FlowResult:
    challenge = args.get("challenge", "").lower()
    logger.info(f"[Flow]select_challenge_handler: {challenge}")
    #Validate challenge by checking if challenge contains one of the following words
    if not any(word in challenge for word in ["fearful", "anxious", "stagnant", "ruminating", "disassociated", "numb", "unhealthy", "scarcity", "excluded", "lack of control", "disembodied", "ungrounded", "obsessed", "silenced", "unheard", "lack of purpose", "unmotivated", "shameful"]):
        return {"status": "error", "message": "Invalid challenge"}
    return {"status": "success", "challenge": challenge}

async def select_challenge_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]select_challenge_callback {result}")
    if result["status"] == "success":
        await flow_manager.set_node("confirm_challenge", sphinx_flow_config["nodes"]["confirm_challenge"])
    else:
        await flow_manager.set_node("select_challenge", sphinx_flow_config["nodes"]["select_challenge"])
    
    
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
        await flow_manager.set_node("record_challenge_in_depth", sphinx_flow_config["nodes"]["challenge_in_depth"])
    else:
        await flow_manager.set_node("select_challenge", sphinx_flow_config["nodes"]["select_challenge"])

async def record_challenge_in_depth_handler(args : FlowArgs) -> FlowResult:
    user_challenge_in_depth = args.get("user_challenge_in_depth", "").lower()
    logger.info(f"[Flow]record_challenge_in_depth_handler {user_challenge_in_depth}")
    return {"status": "success", "user_challenge_in_depth": user_challenge_in_depth}

async def record_challenge_in_depth_callback(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    logger.info(f"[Flow]record_challenge_in_depth_callback {result}")
    if result["user_challenge_in_depth"]:
        # Wait until emotions have been processed
        logger.info("Waiting for emotions to be processed")
        #wait up to 60 seconds
        for _ in range(120):
            await asyncio.sleep(0.5)
            if flow_manager.state.get("emotions_fully_processed", False):
                break
        logger.info("Emotions processed, moving to confirm_emotions")
        await flow_manager.set_node("confirm_emotions", sphinx_flow_config["nodes"]["confirm_emotions"])
    else:
        await flow_manager.set_node("challenge_in_depth", sphinx_flow_config["nodes"]["challenge_in_depth"])

# New handlers for confirming emotions
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
        await flow_manager.set_node("goodbye", sphinx_flow_config["nodes"]["goodbye"])
    else:
        await flow_manager.set_node("challenge_in_depth", sphinx_flow_config["nodes"]["challenge_in_depth"])

sphinx_flow_config = FlowConfig(
    initial_node="greeting",
    nodes={
        "greeting": {
            "role_messages": [
                {"role": "system", "content": "You are Sphinx, a wise, helpful and friendly voice assistant. Keep your responses concise and conversational. Speak slowly and calmly. Always call the provided functions, never skip."},
            ],
            "task_messages": [
                {"role": "system", "content": "Greet the user with a message very similar to this: 'Welcome Seeker! To begin your quest, we invite you to ground and center with a few deep breaths. When you are ready to proceed let me know.'"},
            ],
            "functions": [
                FlowsFunctionSchema(
                    name="check_for_ready",
                    description="Wait for the user to be ready to proceed. When he is ready proceed to collecting his name.",
                    properties={"user_input": {"type": "string", "description": "The user's input"}},
                    required=["user_input"],
                    handler=ready_handler,
                    #transition_to="collect_name"
                    transition_callback=greeting_callback
                )
            ],
            "ui_override": {
                "type": "button",
                "prompt": "Is participant ready?",
                "action_text": "I am ready"
            }
        },
        "collect_name": {
            "task_messages": [
                {"role": "system", "content": "Ask the user for their name."},
            ],
            "functions": [
                FlowsFunctionSchema(
                    name="collect_name",
                    description="Record the user's name.",
                    properties={"name": {"type": "string", "description": "The user's name"}},
                    required=["name"],
                    handler=collect_name_handler,
                    transition_to="consider_challenge"
                )
            ]
        },
        "consider_challenge" : {
            "task_messages": [
                {"role": "system", "content": "Invite the user to consider difficult thought and a specific challenge associated with those thoughts which they have to match to a set of challenges printed on a poster in front of them, using language very similar to this prompt: \
                'Consider your thoughts... Is there one you wish you could avoid, one that calls for attention but makes you feel stuck, disconnected, or out of balance? Is there a current challenge you're facing that is associated with that thought?\
                    Once you have done that, look at the challenges on the poster and let me know which one resonates with you. When you are ready to respond say you are ready or raise your hand to get the attention of a guide.'"}
            ],
            "functions": [
                FlowsFunctionSchema(
                    name="check_for_ready",
                    description="Wait for the user to be ready to proceed",
                    properties={"user_input": {"type": "string", "description": "The user's input"}},
                    required=["user_input"],
                    handler=ready_handler,
                    transition_callback=consider_challenge_callback
                )
            ],
            "ui_override": {
                "type": "button",
                "prompt": "Is participant ready?",
                "action_text": "I am ready"
            }
        },
        "select_challenge": {
            "task_messages": [
                {"role": "system", "content": "Prompt the user : Which challenge listed is most alive for you right now?"}
            ],
            "functions": [
                FlowsFunctionSchema(
                    name="select_challenge",
                    description="Record the user's selected challenge",
                    properties={"challenge": {"type": "string", "description": "The user's selected challenge"}},
                    required=["challenge"],
                    handler=select_challenge_handler,
                    transition_callback=select_challenge_callback,
                )
            ],
            "ui_override": {
                "type": "list",
                "prompt": "Which challenge listed is most alive for you right now?",
                "options": ["Fearful", "Anxious", "Stagnant", "Ruminating", "Disassociated", "Numb", "Unhealthy", "Scarcity", "Excluded", "Lack of Control", "Lack of Agency", "Disembodied", "Ungrounded", "Obsessed", "Silenced", "Unheard", "Lack of Purpose", "Unmotivated", "Shameful"]
            }
        },
        "confirm_challenge": {
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
        },
        "challenge_in_depth" : {
            "task_messages": [
                {"role": "system", "content": "Explore the user's challenge in depth. Example : 'I see you're feeling fearful. What is it like to be going through it?'. After recording the user input giving them ample time to respond, confirm with them if they are done."}
            ],
            "functions": [
                FlowsFunctionSchema(
                    name="record_challenge_in_depth",
                    description="Record the user's challenge in depth. Once recorded, confirm with them if they are done, and move to the next step.",
                    properties={"user_challenge_in_depth": {"type": "string", "description": "The user's own description of their challenge in depth"}},
                    required=["user_challenge_in_depth"],
                    handler=record_challenge_in_depth_handler,
                    transition_callback=record_challenge_in_depth_callback
                )
            ],
            "ui_override": {
                "type": "button",
                "prompt": "Is participant done?",
                "action_text": "I am done"
            }
        },
        "confirm_emotions": {
            "task_messages": [
                {"role": "system", "content": "Emotions Detected: {emotion_summary}. Confirm with the user the emotions detected while he was speaking about the challenge in depth. For example: 'It sounds like you’re feeling {emotion_summary} from experiencing {challenge}. Is that true?'".format(**state)}
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
        },
        "goodbye": {
            "task_messages": [
                {"role": "system", "content": "Say goodbye using the user's name."}
            ],
            "functions": []
        }
    }
)
