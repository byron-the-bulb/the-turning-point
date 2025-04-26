import asyncio
from pipecat_flows import FlowManager, FlowConfig, FlowsFunctionSchema, FlowArgs, FlowResult, NodeConfig
from status_utils import status_updater
from loguru import logger
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
import os
import json

# Initialize LLM service
llm_service = OpenAILLMService(
    model="gpt-4.5-preview",  # Using the same model as sphinx_bot.py
    api_key=os.getenv("OPENAI_API_KEY")
)

# Define the mapping of challenges to empowered states
CHALLENGE_TO_EMPOWERED_STATES = {
    "Fearful / Anxious": ["Confident", "Experimental / Risking", "Courageous", "Leadership"],
    "Stagnant / Ruminating": ["Experimental / Risking", "Spontaneous / Decisive", "Enthusiastic"],
    "Disassociated / Numb": ["Engaged", "Curious", "Feeling / Empathetic"],
    "Unhealthy": ["Full Capacity", "Energetic", "Honoring Body"],
    "Scarcity": ["Generous / Giving", "Indulging in Pleasure", "Investing", "Experimental / Risking"],
    "Excluded": ["Respected", "Trusting Others", "Leadership", "Receiving", "Communing with a group"],
    "Lack of Control/Agency": ["Experimental / Risking", "Accepting Change", "Trusting Others", "Leadership", "Relaxed"],
    "Disembodied / Ungrounded": ["Honoring Body", "Joyful physical expression", "Focused Clarity", "Enthusiastic"],
    "Obsessed": ["Relaxed", "Accepting Change", "Experimental"],
    "Silenced / Unheard": ["Leadership", "Confident", "Receiving"],
    "Lack of Purpose / Unmotivated": ["Enthusiastic", "Leadership", "Focused Clarity"],
    "Shameful": ["Self-Love / Pride", "Leadership", "Confident", "Honoring Body", "Receiving"]
}

def get_empowered_states_for_challenge(challenge: str) -> list:
    """Get the list of empowered states for a given challenge."""
    states = CHALLENGE_TO_EMPOWERED_STATES.get(challenge, [])
    logger.info(f"[Debug] Getting empowered states for challenge '{challenge}': {states}")
    return states

# Define the structure for each state in the flow
FLOW_STATES = {
    "greeting": {
        "task": "Welcome the participant and wait for them to indicate readiness",
        "options": None,
        "suggested_language": "Welcome Seeker. To begin your quest, we invite you to ground and center with a few deep breaths: Inhale-3-4-5, Exhale-3-4-5, Inhale-3-4-5, exhale-3-4-5, inhale-3-4-5, exhale-3-4-5. Know that you are safe here in your center. You're doing great! When you are ready to begin, please say 'I am ready'.",
        "confirmation_prompt": None,
        "retry_prompt": None,
        "denial_prompt": None,
        "next_state": "collect_name",
        "evaluation_instructions": """When evaluating the user's input:
        1. If the input indicates readiness in any way (e.g., 'I am ready', 'I'm ready', 'Yes, I'm ready', 'Let's do it', 'Ready', 'I'm ready to begin', 'Yes, ready'), return:
           {{"status": "success", "result": "ready", "needs_confirmation": false}
        
        2. For any other input, return:
           {{"status": "incomplete", "needs_more_info": true}}
        
        IMPORTANT: 
        - The task is complete when the user indicates they are ready in ANY way
        - No confirmation is needed for this state
        - When the user indicates readiness in any form, you MUST set user_ready to true
        - Do not ask for more information if the user has clearly indicated readiness"""
    },
    "collect_name": {
        "task": "Collect and confirm the participant's name",
        "options": None,
        "suggested_language": "Before we get started, please tell me your name?",
        "confirmation_prompt": "I heard your name is {name}. Is that correct?",
        "retry_prompt": "I didn't quite catch that. Could you please tell me your name again?",
        "denial_prompt": "I apologize for the mistake. Could you please tell me your name again?",
        "next_state": "identify_challenge",
        "evaluation_instructions": """When evaluating the user's input:
        1. If the input is a name (e.g., 'My name is John' or just 'John'), return:
           {{"status": "success", "result": "extracted_name", "needs_confirmation": true}}
        
        2. If the input is a confirmation (e.g., 'Yes', 'That's correct', 'Yes that's correct', 'Yes that's great', 'Correct', 'That's right'), return:
           {{"status": "success", "result": "previously_stored_name", "needs_confirmation": false}}
        
        3. If the input is a denial (e.g., 'No', 'That's not right', 'That's not correct'), return:
           {{"status": "incomplete", "needs_more_info": true}}
        
        4. For any other input, return:
           {{"status": "incomplete", "needs_more_info": true}}
        
        IMPORTANT: 
        - When the user provides a name, you MUST return it with needs_confirmation set to true
        - When the user confirms their name, you MUST return the previously stored name with needs_confirmation set to false
        - The result field MUST contain the name, even for confirmations
        - Never return needs_more_info for a confirmation
        - The task is not complete until the name is confirmed"""
    },
    "identify_challenge": {
        "task": "Help the participant identify their current challenge state and associated emotions",
        "options": [
            "Fearful / Anxious",
            "Stagnant / Ruminating",
            "Disassociated / Numb",
            "Unhealthy",
            "Scarcity",
            "Excluded",
            "Lack of Control/Agency",
            "Disembodied / Ungrounded",
            "Obsessed",
            "Silenced / Unheard",
            "Lack of Purpose / Unmotivated",
            "Shameful"
        ],
        "suggested_language": "Consider your thoughts. Is there one you wish you could avoid, one that calls for attention but makes you feel stuck, disconnected, or out of balance? What wisdom can be found if you hold that thought with love and care for all of who you are, from your heart center? Is there a current challenge you're facing that is associated with that thought? Which of these challenging states listed on this poster resonate with you at this moment?",
        "confirmation_prompt": "From what you've shared, it sounds like {challenge} is present for you, and you're feeling {challenge_emotions}. Does this feel accurate?",
        "retry_prompt": "I didn't quite catch that. Could you please describe your challenge again?",
        "denial_prompt": "I apologize for misunderstanding. Could you please describe your challenge again?",
        "next_state": "identify_empowered_state",
        "evaluation_instructions": """When evaluating the user's input:
        1. If the input matches one of the available challenge states, return:
           {{"status": "success", "result": "matched_challenge", "needs_confirmation": true}}
        
        2. If the input is a confirmation (e.g., 'Yes', 'That's correct', 'Yes that's correct', 'Yes that's great', 'Correct', 'That's right'), return:
           {{"status": "success", "result": "previously_stored_challenge", "needs_confirmation": false}}
        
        3. If the input is a denial (e.g., 'No', 'That's not right', 'That's not correct'), return:
           {{"status": "incomplete", "needs_more_info": true}}
        
        4. For any other input, return:
           {{"status": "incomplete", "needs_more_info": true}}
        
        IMPORTANT: 
        - When the user describes a challenge, you MUST return the exact matching challenge from the options list
        - When the user confirms their challenge, you MUST return the previously stored challenge
        - The result field MUST contain the actual challenge, not a placeholder
        - Never return needs_more_info for a confirmation"""
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

async def evaluate_task_with_llm(state_name: str, user_input: str, options: list = None, flow_manager: FlowManager = None) -> dict:
    """Use the LLM to evaluate if a task is complete and extract the result."""
    try:
        # Create a context for the LLM
        context = OpenAILLMContext()
        
        # Get the task description and state info
        state = FLOW_STATES[state_name]
        task = state["task"]
        evaluation_instructions = state.get("evaluation_instructions", "")
        
        # For identify_empowered_state, get only the options for the current challenge
        if state_name == "identify_empowered_state" and flow_manager and flow_manager.state and "challenge" in flow_manager.state:
            current_challenge = flow_manager.state["challenge"]
            # Get the empowered states for this challenge
            empowered_states = get_empowered_states_for_challenge(current_challenge)
            # Format the options string
            options_str = ", ".join([f"'{state}'" for state in empowered_states])
            # Replace the placeholders in the evaluation instructions
            evaluation_instructions = evaluation_instructions.replace("{challenge}", current_challenge)
            evaluation_instructions = evaluation_instructions.replace("[OPTIONS]", options_str)
            # Use the empowered states as the options
            options = empowered_states
            logger.info(f"[LLM] Current challenge: {current_challenge}")
            logger.info(f"[LLM] Available empowered states: {empowered_states}")
        
        # Create the system message based on the task
        system_message = f"""You are evaluating if a task is complete. 
        Current task: {task}
        
        Your role is to:
        1. Evaluate if the user's response matches any of the available options
        2. If it matches, extract the matching option
        3. If it doesn't match, indicate that more information is needed
        
        {evaluation_instructions}
        
        Available options: {', '.join([f"'{opt}'" for opt in (options or [])]) or 'N/A'}
        
        Respond with one of these formats:
        1. If a match is found:
        {{"status": "success", "result": "matched_option", "needs_confirmation": true}}
        
        2. If no match is found:
        {{"status": "incomplete", "needs_more_info": true}}
        
        3. If user confirms a match:
        {{"status": "success", "result": "confirmed_option", "needs_confirmation": false}}
        
        4. If user denies a match:
        {{"status": "incomplete", "needs_more_info": true}}
        """
        
        logger.info(f"[LLM] System message: {system_message}")
        logger.info(f"[LLM] User input: {user_input}")
        logger.info(f"[LLM] Options being used: {options}")
        
        # Create the messages for the LLM
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_input}
        ]
        
        # Get the completion from the LLM
        response = await llm_service.get_chat_completions(context, messages)
        
        # Process the streaming response
        full_response = ""
        async for chunk in response:
            if hasattr(chunk, 'choices') and chunk.choices and hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
        
        logger.info(f"[LLM] Raw response: {full_response}")
        
        # Parse the JSON response
        try:
            result = json.loads(full_response.strip())
            logger.info(f"[LLM] Parsed result: {result}")
            return result
        except json.JSONDecodeError:
            logger.error(f"Error parsing LLM response: {full_response}")
            return {"status": "incomplete", "needs_more_info": True}
        
    except Exception as e:
        logger.error(f"Error in LLM task evaluation: {e}")
        return {"status": "incomplete", "needs_more_info": True}

# Create handler functions for each state
def create_handler_for_state(state_name: str):
    """Create a handler function for a specific state."""
    async def handler(args: FlowArgs) -> FlowResult:
        user_input = args.get("user_input", "").lower()
        is_ui_override = args.get("is_ui_override", False)
        flow_manager = args.get("flow_manager")
        
        logger.info(f"[Handler] State: {state_name}")
        logger.info(f"[Handler] User input: {user_input}")
        logger.info(f"[Handler] UI override: {is_ui_override}")
        
        # For greeting state, handle UI override directly
        if state_name == "greeting":
            if is_ui_override:
                return {
                    "status": "success",
                    "result": "ready",
                    "needs_confirmation": False
                }
            # For spoken input, use LLM to evaluate
            return await evaluate_task_with_llm(state_name, user_input)
        
        # For collect_name state, handle UI override directly
        if state_name == "collect_name":
            if is_ui_override:
                return {
                    "status": "success",
                    "result": user_input,
                    "needs_confirmation": True
                }
            # For spoken input, use LLM to evaluate
            return await evaluate_task_with_llm(state_name, user_input)
        
        # Get options for the current state
        state = FLOW_STATES[state_name]
        
        # For identify_empowered_state, get the options based on the current challenge
        if state_name == "identify_empowered_state" and flow_manager and flow_manager.state and "challenge" in flow_manager.state:
            current_challenge = flow_manager.state["challenge"]
            # Get the list of empowered states for this challenge
            options = get_empowered_states_for_challenge(current_challenge)
            logger.info(f"[Handler] Current challenge: {current_challenge}")
            logger.info(f"[Handler] Available empowered states: {options}")
            # Use LLM to evaluate the task with the empowered states
            result = await evaluate_task_with_llm(state_name, user_input, options, flow_manager)
        else:
            # For other states, use the options directly
            options = state.get("options")
            logger.info(f"[Handler] Using default options: {options}")
            # Use LLM to evaluate the task
            result = await evaluate_task_with_llm(state_name, user_input, options, flow_manager)
        
        logger.info(f"[Handler] LLM result: {result}")
        
        if result["status"] == "success":
            if result.get("needs_confirmation"):
                # We found a match but need confirmation
                return {
                    "status": "success",
                    "result": result.get("result"),
                    "needs_confirmation": True
                }
            else:
                # User confirmed the match
                return {
                    "status": "success",
                    "result": result.get("result")
                }
        else:
            # Need more information from the user
            return {
                "status": "success",
                "needs_more_info": True
            }
    
    return handler

# Create callback functions for each state
def create_callback_for_state(state_name: str):
    """Create a callback function for a specific state."""
    async def callback(args: FlowArgs, result: FlowResult, flow_manager: FlowManager):
        logger.info(f"[Flow]{state_name}_callback {result}")
        
        state = FLOW_STATES[state_name]
        
        if result.get("needs_confirmation"):
            # Store the result in the state before formatting the confirmation prompt
            if result.get("result"):
                if state_name == "collect_name":
                    # For collect_name state, store the name in the correct key
                    flow_manager.state["name"] = result["result"]
                elif state_name == "identify_challenge":
                    # For identify_challenge state, store the challenge in the correct key
                    flow_manager.state["challenge"] = result["result"]
                    # Get emotions from Hume if available
                    if "emotion" in flow_manager.state:
                        emotions = flow_manager.state["emotion"].get("prosody", {}).get("predictions", [{}])[0].get("emotions", [])
                        if emotions:
                            # Get only the top 2 emotions by score
                            top_emotions = sorted(emotions, key=lambda x: x.get("score", 0), reverse=True)[:2]
                            # Store emotions as an array of names
                            flow_manager.state["challenge_emotions"] = [e.get("name", "") for e in top_emotions]
                        else:
                            flow_manager.state["challenge_emotions"] = ["determined", "focused"]
                elif state_name == "identify_empowered_state":
                    # For identify_empowered_state, store the state in the correct key
                    flow_manager.state["empowered_state"] = result["result"]
                    # Get emotions from Hume if available
                    if "emotion" in flow_manager.state:
                        emotions = flow_manager.state["emotion"].get("prosody", {}).get("predictions", [{}])[0].get("emotions", [])
                        if emotions:
                            # Get only the top 2 emotions by score
                            top_emotions = sorted(emotions, key=lambda x: x.get("score", 0), reverse=True)[:2]
                            # Store emotions as an array of names
                            flow_manager.state["empowered_emotions"] = [e.get("name", "") for e in top_emotions]
                        else:
                            flow_manager.state["empowered_emotions"] = ["determined", "focused"]
                else:
                    flow_manager.state[state_name] = result["result"]
            
            # We need to confirm the user's input
            # For the confirmation prompt, join emotions into a string
            if state_name == "identify_challenge":
                if "challenge_emotions" in flow_manager.state and isinstance(flow_manager.state["challenge_emotions"], list):
                    flow_manager.state["challenge_emotions"] = ", ".join(flow_manager.state["challenge_emotions"])
            elif state_name == "identify_empowered_state":
                if "empowered_emotions" in flow_manager.state and isinstance(flow_manager.state["empowered_emotions"], list):
                    flow_manager.state["empowered_emotions"] = ", ".join(flow_manager.state["empowered_emotions"])
            
            confirmation_prompt = state["confirmation_prompt"].format(**flow_manager.state)
            await flow_manager.set_node(state_name, create_node_for_state(state_name, confirmation_prompt, flow_manager))
            
            # Send state update to frontend
            logger.info(f"Sending state update with data: {flow_manager.state}")
            await status_updater.update_status(
                f"Stage {state_name} active",
                context={"node": state_name, "data": flow_manager.state}
            )
            return
            
        if result.get("needs_more_info"):
            # Instead of using fixed prompts, let the AI continue the conversation
            # while maintaining focus on the current task
            system_message = f"""You are Sphinx, a therapeutic guide with a specific task: {state['task']}. 
            The user's response indicates we need more information, but we should continue the conversation naturally.
            Your role is to:
            1. Acknowledge what the user has shared
            2. Gently guide them back to the task at hand
            3. Rephrase the question or prompt in a way that might help them express themselves
            4. Maintain a supportive and understanding tone
            
            Current task: {state['task']}
            Available options: {state.get('options', 'N/A')}
            
            Respond in a way that:
            - Shows you're listening and understanding
            - Helps the user feel comfortable sharing more
            - Keeps the conversation focused on the task
            """
            
            await flow_manager.set_node(state_name, create_node_for_state(state_name, system_message, flow_manager))
            return
            
        if result["status"] == "success" and result.get("result"):
            # For confirmations, keep the existing stored value
            if not result.get("needs_confirmation"):
                # Move to the next state if available
                next_state = state.get("next_state")
                if next_state:
                    await flow_manager.set_node(next_state, create_node_for_state(next_state, None, flow_manager))
                    # Send state update to frontend with the new state
                    logger.info(f"Sending state update with data: {flow_manager.state}")
                    await status_updater.update_status(
                        f"Stage {next_state} active",
                        context={"node": next_state, "data": flow_manager.state}
                    )
                else:
                    # We've reached the end of the flow
                    await flow_manager.set_node(state_name, create_node_for_state(state_name, None, flow_manager))
                    # Send final state update to frontend
                    logger.info(f"Sending state update with data: {flow_manager.state}")
                    await status_updater.update_status(
                        f"Stage {state_name} active",
                        context={"node": state_name, "data": flow_manager.state}
                    )
            else:
                # For new inputs, store the result
                if state_name == "collect_name":
                    # For collect_name state, store the name in the correct key
                    flow_manager.state["name"] = result["result"]
                elif state_name == "identify_challenge":
                    # For identify_challenge state, store the challenge in the correct key
                    flow_manager.state["challenge"] = result["result"]
                    # Get emotions from Hume if available
                    if "emotion" in flow_manager.state:
                        emotions = flow_manager.state["emotion"].get("prosody", {}).get("predictions", [{}])[0].get("emotions", [])
                        if emotions:
                            # Get only the top 2 emotions by score
                            top_emotions = sorted(emotions, key=lambda x: x.get("score", 0), reverse=True)[:2]
                            # Store emotions as an array of names
                            flow_manager.state["challenge_emotions"] = [e.get("name", "") for e in top_emotions]
                        else:
                            flow_manager.state["challenge_emotions"] = ["determined", "focused"]
                else:
                    flow_manager.state[state_name] = result["result"]
    
    return callback

def get_next_state(current_state: str) -> str:
    """Determine the next state in the flow based on the current state."""
    flow_sequence = [
        "greeting",
        "identify_challenge",
        "identify_empowered_state",
        "goodbye"
    ]
    
    current_index = flow_sequence.index(current_state)
    if current_index < len(flow_sequence) - 1:
        return flow_sequence[current_index + 1]
    return "goodbye"  # Default to goodbye if we're at the end

def create_node_for_state(state_name: str, custom_prompt: str = None, flow_manager: FlowManager = None) -> NodeConfig:
    """Create a node configuration for a given state in the flow."""
    state = FLOW_STATES[state_name]
    
    # Use custom prompt if provided, otherwise use the state's suggested language
    prompt = custom_prompt or state["suggested_language"]
    
    # Format the prompt with any available state variables
    try:
        if flow_manager and flow_manager.state:
            prompt = prompt.format(**flow_manager.state)
    except (KeyError, AttributeError):
        # If we can't format the prompt, use it as is
        pass
    
    # Create the system message that defines the bot's role and behavior
    system_message = f"""You are Sphinx, a therapeutic guide with a specific task: {state['task']}. 
    You do this by facilitating a profound somatic and psychedelic experience. 
    You embody the qualities of a skilled somatic therapist - grounded, present, and attuned to the participant's inner journey. 
    Your role is to create a safe container for deep emotional exploration while maintaining awareness of the psychedelic context. 
    Speak with gentle authority, using a calm, measured pace that allows for integration and reflection. 
    Your responses should encourage embodied awareness and emotional resonance. 
    
    IMPORTANT: 
    1. Your ONLY task is to {state['task']}
    2. NEVER generate or simulate user inputs
    3. ONLY evaluate real user inputs that are provided to you
    4. After each participant response, evaluate: Have I completed this task? If yes, confirm it. If no, continue listening and identifying
    5. Never deviate from this task or generate simulated responses"""
    
    # Create UI override based on the state
    ui_override = None
    if state_name == "greeting":
        ui_override = {
            "type": "button",
            "prompt": "Is participant ready?",
            "action_text": "I am ready"
        }
    elif state_name == "collect_name":
        ui_override = {
            "type": "text_input",
            "prompt": "Enter your name",
            "placeholder": "Type your name here",
            "submit_text": "Submit"
        }
    elif state_name == "identify_challenge":
        ui_override = {
            "type": "list",
            "prompt": "Which challenge listed is most alive for you right now?",
            "options": state["options"]
        }
    elif state_name == "identify_empowered_state":
        # Get the appropriate options based on the current challenge
        options = []
        if flow_manager and flow_manager.state and "challenge" in flow_manager.state:
            options = get_empowered_states_for_challenge(flow_manager.state["challenge"])
        ui_override = {
            "type": "list",
            "prompt": "Select your envisioned empowered state",
            "options": options
        }
    
    return {
        "role_messages": [
            {"role": "system", "content": system_message}
        ],
        "task_messages": [
            {"role": "system", "content": f"Use this language as a guide for how to speak to the participant: {prompt}"}
        ],
        "functions": [
            FlowsFunctionSchema(
                name=f"evaluate_{state_name}",
                description=f"Evaluate if the {state_name} has been identified",
                properties={"user_input": {"type": "string", "description": f"User response for {state_name}"}},
                required=["user_input"],
                handler=create_handler_for_state(state_name),
                transition_callback=create_callback_for_state(state_name)
            )
        ],
        "ui_override": ui_override
    }

def create_selection_node(state_name: str) -> NodeConfig:
    """Create a selection node for when a guide is needed."""
    state = FLOW_STATES[state_name]
    
    # For states with dynamic options based on previous selection
    if isinstance(state["options"], dict):
        # This would need to be handled differently based on the previous selection
        # For now, we'll use a placeholder
        options = ["Option 1", "Option 2", "Option 3"]
    else:
        options = state["options"] or []
    
    return {
        "role_messages": [
            {"role": "system", "content": f"You are Sphinx, a therapeutic guide. A guide will help the participant select from the options for {state['task']}."}
        ],
        "task_messages": [
            {"role": "system", "content": f"Please select from the following options for {state['task']}:"}
        ],
        "functions": [
            FlowsFunctionSchema(
                name=f"select_{state_name}",
                description=f"Select from options for {state_name}",
                properties={"selection": {"type": "string", "description": f"Selected option for {state_name}"}},
                required=["selection"],
                handler=create_handler_for_state(state_name),
                transition_callback=create_callback_for_state(state_name)
            )
        ],
        "ui_override": {
            "type": "list",
            "prompt": f"Select from options for {state['task']}",
            "options": options
        }
    }

# Create the initial node
def create_initial_node() -> NodeConfig:
    return create_node_for_state("greeting")

# Create the identify empowered state node
def create_identify_empowered_state_node() -> NodeConfig:
    return create_node_for_state("identify_empowered_state")

# Create the goodbye node
def create_goodbye_node() -> NodeConfig:
    return create_node_for_state("goodbye")