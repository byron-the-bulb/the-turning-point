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
    #Validate challenge
    if challenge not in ["fearful", "anxious", "stagnant", "ruminating", "disassociated", "numb", "unhealthy", "scarcity", "excluded", "lack of control", "disembodied", "ungrounded", "obsessed", "silenced", "unheard", "lack of purpose", "unmotivated", "shameful"]:
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
        await flow_manager.set_node("goodbye", sphinx_flow_config["nodes"]["goodbye"])
    else:
        await flow_manager.set_node("select_challenge", sphinx_flow_config["nodes"]["select_challenge"])

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
                    description="Wait for the user to be ready to proceed",
                    properties={"user_input": {"type": "string", "description": "The user's input"}},
                    required=["user_input"],
                    handler=ready_handler,
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
                    description="Record the user's name",
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
        "goodbye": {
            "task_messages": [
                {"role": "system", "content": "Say goodbye using the user's name."}
            ],
            "functions": []
        }
    }
)

