from pipecat_flows import FlowManager, FlowConfig, FlowsFunctionSchema, FlowArgs, FlowResult
from pipecat.frames.frames import TextFrame
from status_utils import status_updater

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
    print("ready_handler", args)
    # Update status directly via API
    await status_updater.update_status(
        "Waiting for user to be ready",
        {"node": "ready"}
    )
    user_input = args.get("user_input", "").lower()
    is_ready = any(word in user_input for word in ["ready", "proceed", "continue", "yes"])
    return {"status": "success", "user_ready": is_ready}

async def handle_user_readiness(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    print("handle_user_readiness", result)
    if result["user_ready"]:
        # Update status directly via API
        await status_updater.update_status(
            "Moving to name collection phase",
            {"node": "collect_name"}
        )
        
        await flow_manager.set_node("collect_name", sphinx_flow_config["nodes"]["collect_name"])
    else:
        # Update status directly via API
        await status_updater.update_status(
            "Remaining in greeting phase until user is ready",
            {"node": "greeting"}
        )
        
        # Stay on the current node if the user is not ready
        await flow_manager.set_node("greeting", sphinx_flow_config["nodes"]["greeting"])

async def handle_user_readiness_meditation(
    args: FlowArgs,
    result: FlowResult,
    flow_manager: FlowManager
):
    print("handle_user_readiness_meditation")
    if result["user_ready"]:
        # Update status directly via API
        await status_updater.update_status(
            "Moving to challenge selection phase",
            {"node": "select_challenge"}
        )
        
        await flow_manager.set_node("select_challenge", sphinx_flow_config["nodes"]["select_challenge"])
    else:
        # Update status directly via API
        await status_updater.update_status(
            "Continuing guided meditation until user is ready",
            {"node": "guided_meditation"}
        )
        
        # Stay on the current node if the user is not ready
        await flow_manager.set_node("guided_meditation", sphinx_flow_config["nodes"]["guided_meditation"])

async def collect_challenge_handler(args : FlowArgs) -> FlowResult:
    challenge = args["challenge"]
    print("collect_challenge_handler", challenge)
    #Validate challenge
    if challenge not in ["Fearful", "Anxious", "Stagnant", "Ruminating", "Disassociated", "Numb", "Unhealthy", "Scarcity", "Excluded", "Lack of Control", "Disembodied", "Ungrounded", "Obsessed", "Silenced", "Unheard", "Lack of Purpose", "Unmotivated", "Shameful"]:
        return {"status": "error", "message": "Invalid challenge"}
    return {"status": "success", "challenge": challenge}

sphinx_flow_config = FlowConfig(
    initial_node="greeting",
    nodes={
        "greeting": {
            "role_messages": [
                {"role": "system", "content": "You are Sphinx, a helpful and friendly voice assistant. Keep your responses concise and conversational."},
            ],
            "task_messages": [
                {"role": "system", "content": "Greet the user with a message very similar to this: 'Welcome Seeker. To begin your quest, we invite you to ground and center with a few deep breaths. When you are ready to preceed let me know.'"},

            ],
            "functions": [
                FlowsFunctionSchema(
                    name="check_for_ready",
                    description="Wait for the user to be ready to proceed",
                    properties={"user_input": {"type": "string", "description": "The user's input"}},
                    required=["user_input"],
                    handler=ready_handler,
                    transition_callback=handle_user_readiness
                )
            ]
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
                    transition_to="guided_meditation"
                )
            ]
        },
        "guided_meditation" : {
            "task_messages": [
                {"role": "system", "content": "Invite the user to consider the following:\
                    'Consider your thoughts. Is there one you wish you could avoid, one that calls for attention but makes you feel stuck, disconnected, or out of balance?.\
                    Is there a current challenge you're facing that is associated with that thought?\
                    When you are ready to speak your truth let me know.'\
                    When the user says they are ready always call the handle_user_readiness_meditation function.\
                    "}
            ],
            "functions": [
                FlowsFunctionSchema(
                    name="check_for_ready",
                    description="Wait for the user to be ready to proceed",
                    properties={"user_input": {"type": "string", "description": "The user's input"}},
                    required=["user_input"],
                    handler=ready_handler,
                    transition_callback=handle_user_readiness_meditation
                )
            ]
        },
        "select_challenge": {
            "task_messages": [
                {"role": "system", "content": "Ask the user to select a challenge from the list, in this fashion : Which of these challenging states listed on the poster resonate with you at this moment?\
                    The challenge must be one of the following: Fearful, Anxious, Stagnant , Ruminating, Disassociated, Numb, Unhealthy, Scarcity, Excluded, Lack of Control, Lack of Agency, Disembodied, Ungrounded, Obsessed, Silenced, Unheard, Lack of Purpose, Unmotivated, Shameful."}
            ],
            "functions": [
                FlowsFunctionSchema(
                    name="select_challenge",
                    description="Record the user's selected challenge",
                    properties={"challenge": {"type": "string", "description": "The user's selected challenge"}},
                    required=["challenge"],
                    handler=collect_challenge_handler,
                    transition_to="goodbye"
                )
            ]
        },
        "goodbye": {
            "task_messages": [
                {"role": "system", "content": "Say goodbye using the user's name."}
            ],
            "functions": []
        }
    }
)

