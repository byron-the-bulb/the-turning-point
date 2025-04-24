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

# Define the structure for each state in the flow
FLOW_STATES = {
    "greeting": {
        "task": "Welcome the participant and create a safe, somatic space",
        "options": None,
        "suggested_language": "Welcome Seeker. To begin your quest, we invite you to ground and center with a few deep breaths: Inhale-3-4-5, Exhale-3-4-5, Inhale-3-4-5, exhale-3-4-5, inhale-3-4-5, exhale-3-4-5. Know that you are safe here in your center. You're doing great! What is your name?",
        "confirmation_prompt": "I heard your name is {name}. Is that correct?",
        "retry_prompt": "I didn't quite catch that. Could you please tell me your name again?",
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
        - When the user confirms their name, you MUST return the previously stored name with needs_confirmation set to false
        - The result field MUST contain the name, even for confirmations
        - Never return needs_more_info for a confirmation"""
    },
    "identify_challenge": {
        "task": "Help the participant identify their current challenge state",
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
        "confirmation_prompt": "From what you've shared, it sounds like {challenge} is present for you. Does this feel accurate?",
        "next_state": "record_challenge_feeling",
        "evaluation_instructions": "Match the user's description to one of the available challenge states. If a match is found, return it as the result. If no clear match is found, indicate more information is needed."
    },
    "record_challenge_feeling": {
        "task": "Guide the participant in describing their challenge experience",
        "options": None,
        "suggested_language": "Please describe what this challenge is like for you. When you are ready to speak your truth, hold your hand out and your guide will start your interactive AI recording sequence. Don't worry, these recordings are only for our system – they will not be saved or shared with any person or 3rd party.",
        "confirmation_prompt": "Would you like to share more about how this challenge affects you?",
        "next_state": "confirm_challenge_emotions"
    },
    "confirm_challenge_emotions": {
        "task": "Help the participant identify emotions associated with their challenge",
        "options": [
            "Admiration", "Adoration", "Aesthetic Appreciation", "Amusement", "Anger", "Anxiety", "Awe", "Awkwardness", "Boredom", "Calmness", "Concentration", "Confusion", "Contemplation", "Contempt", "Contentment", "Craving", "Desire", "Determination", "Disappointment", "Disgust", "Distress", "Doubt", "Ecstasy", "Embarrassment", "Empathic Pain", "Entrancement", "Envy", "Excitement", "Fear", "Guilt", "Horror", "Interest", "Joy", "Love", "Nostalgia", "Pain", "Pride", "Realization", "Relief", "Romance", "Sadness", "Satisfaction", "Shame", "Surprise", "Sympathy", "Tiredness", "Triumph", "Vulnerability", "Worry"
        ],
        "suggested_language": "It sounds like you're feeling {emotions} from experiencing {challenge}. Is that true? If not, do any of these words describe your feelings?",
        "confirmation_prompt": "Would you like to explore any other emotions you're experiencing?",
        "next_state": "identify_envisioned_state"
    },
    "identify_envisioned_state": {
        "task": "Guide the participant in envisioning their desired future state",
        "options": {
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
        },
        "suggested_language": "What if your challenges are just the beginning of a quest? What treasures will you gain along the way? Envisioning what you seek will help you find your path. When you have passed through this challenge, what will you be like? How will you feel? How will you live your life on the other side of this experience?",
        "confirmation_prompt": "It sounds like you will feel {envisioned_state}. Is this correct? If not, can you choose one or more states or feelings from this list that you imagine you will experience because you transformed through this challenge?",
        "next_state": "confirm_envisioned_emotions"
    },
    "confirm_envisioned_emotions": {
        "task": "Help the participant identify emotions associated with their envisioned state",
        "options": [
            "Admiration", "Adoration", "Aesthetic Appreciation", "Amusement", "Anger", "Anxiety", "Awe", "Awkwardness", "Boredom", "Calmness", "Concentration", "Confusion", "Contemplation", "Contempt", "Contentment", "Craving", "Desire", "Determination", "Disappointment", "Disgust", "Distress", "Doubt", "Ecstasy", "Embarrassment", "Empathic Pain", "Entrancement", "Envy", "Excitement", "Fear", "Guilt", "Horror", "Interest", "Joy", "Love", "Nostalgia", "Pain", "Pride", "Realization", "Relief", "Romance", "Sadness", "Satisfaction", "Shame", "Surprise", "Sympathy", "Tiredness", "Triumph", "Vulnerability", "Worry"
        ],
        "suggested_language": "I sense that {emotions} are present in your vision of your future state. Does this resonate with you?",
        "confirmation_prompt": "Would you like to explore any other emotions you envision experiencing?",
        "next_state": "goodbye"
    },
    "goodbye": {
        "task": "Conclude the session and prepare for video experience",
        "options": None,
        "suggested_language": "Thank you for sharing and taking the time to explore your inner landscape! Now please let your guide know you are ready to view your destiny.",
        "confirmation_prompt": None,
        "next_state": None
    }
}

async def evaluate_task_with_llm(state_name: str, user_input: str, options: list = None) -> dict:
    """Use the LLM to evaluate if the task is complete and extract the result."""
    try:
        # Create a context for the LLM
        context = OpenAILLMContext()
        
        # Get the task description and state info
        state = FLOW_STATES[state_name]
        task = state["task"]
        evaluation_instructions = state.get("evaluation_instructions", "")
        
        # Create the system message based on the task
        system_message = f"""You are a therapeutic guide evaluating if a task is complete. 
        Current task: {task}
        
        Your role is to:
        1. Evaluate if the user's response matches any of the available options
        2. If it matches, extract the matching option
        3. If it doesn't match, indicate that more information is needed
        
        {evaluation_instructions}
        
        Available options: {', '.join(options) if options else 'N/A'}
        
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
        
        # Parse the JSON response
        try:
            result = json.loads(full_response.strip())
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
        
        # For greeting state, we don't need to evaluate anything until we get user input
        if state_name == "greeting":
            if not user_input:
                return {
                    "status": "success",
                    "user_ready": False
                }
            # Check if this is a UI override action
            if user_input == "i am ready":
                return {
                    "status": "success",
                    "user_ready": True
                }
        
        # Get options for the current state
        state = FLOW_STATES[state_name]
        options = state.get("options")
        
        # Use LLM to evaluate the task
        result = await evaluate_task_with_llm(state_name, user_input, options)
        
        if result["status"] == "success":
            if result.get("needs_confirmation"):
                # We found a match but need confirmation
                return {
                    "status": "success",
                    "user_ready": False,
                    "result": result.get("result"),
                    "needs_confirmation": True
                }
            else:
                # User confirmed the match
                return {
                    "status": "success",
                    "user_ready": True,
                    "result": result.get("result")
                }
        else:
            # Need more information from the user
            return {
                "status": "success",
                "user_ready": False,
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
                if state_name == "greeting":
                    # For greeting state, store the name in the correct key
                    flow_manager.state["name"] = result["result"]
                elif state_name == "identify_challenge":
                    # For identify_challenge state, store the challenge in the correct key
                    flow_manager.state["challenge"] = result["result"]
                else:
                    flow_manager.state[state_name] = result["result"]
            
            # We need to confirm the user's input
            confirmation_prompt = state["confirmation_prompt"].format(**flow_manager.state)
            await flow_manager.set_node(state_name, create_node_for_state(state_name, confirmation_prompt))
            return
            
        if result.get("needs_more_info"):
            # We need more information from the user
            if state_name == "greeting" and "name" in flow_manager.state:
                # If we're in greeting and have a previous name attempt, use the retry prompt
                await flow_manager.set_node(state_name, create_node_for_state(state_name, state["retry_prompt"]))
            else:
                # Otherwise use the standard prompt
                await flow_manager.set_node(state_name, create_node_for_state(state_name))
            return
            
        if result["status"] == "success" and result.get("result"):
            # Store the result in the state
            if state_name == "greeting":
                # For greeting state, store the name in the correct key
                flow_manager.state["name"] = result["result"]
            elif state_name == "identify_challenge":
                # For identify_challenge state, store the challenge in the correct key
                flow_manager.state["challenge"] = result["result"]
            else:
                flow_manager.state[state_name] = result["result"]
            
            # Move to the next state if available
            next_state = state.get("next_state")
            if next_state:
                await flow_manager.set_node(next_state, create_node_for_state(next_state))
            else:
                # We've reached the end of the flow
                await flow_manager.set_node(state_name, create_node_for_state(state_name))
    
    return callback

def get_next_state(current_state: str) -> str:
    """Determine the next state in the flow based on the current state."""
    flow_sequence = [
        "greeting",
        "identify_challenge",
        "record_challenge_feeling",
        "confirm_challenge_emotions",
        "identify_envisioned_state",
        "confirm_envisioned_emotions",
        "goodbye"
    ]
    
    current_index = flow_sequence.index(current_state)
    if current_index < len(flow_sequence) - 1:
        return flow_sequence[current_index + 1]
    return "goodbye"  # Default to goodbye if we're at the end

def create_node_for_state(state_name: str, custom_prompt: str = None) -> NodeConfig:
    """Create a node configuration for a given state in the flow."""
    state = FLOW_STATES[state_name]
    
    # Use custom prompt if provided, otherwise use the state's suggested language
    prompt = custom_prompt or state["suggested_language"]
    
    # Format the prompt with any available state variables
    try:
        # Get the flow manager from the global scope if available
        flow_manager = globals().get('flow_manager')
        if flow_manager:
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
        "ui_override": {
            "type": "button",
            "prompt": "Is participant ready?",
            "action_text": "I am ready"
        }
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

# Create the consider challenge node
def create_consider_challenge_node() -> NodeConfig:
    return create_node_for_state("identify_challenge")

# Create the confirm challenge node
def create_confirm_challenge_node() -> NodeConfig:
    return create_node_for_state("confirm_challenge")

# Create the record challenge feeling node
def create_record_challenge_feeling_node() -> NodeConfig:
    return create_node_for_state("record_challenge_feeling")

# Create the confirm challenge emotions node
def create_confirm_challenge_emotions_node() -> NodeConfig:
    return create_node_for_state("confirm_challenge_emotions")

# Create the identify envisioned state node
def create_identify_envisioned_state_node() -> NodeConfig:
    return create_node_for_state("identify_envisioned_state")

# Create the confirm envisioned state node
def create_confirm_envisioned_state_node() -> NodeConfig:
    return create_node_for_state("confirm_envisioned_state")

# Create the confirm envisioned emotions node
def create_confirm_envisioned_emotions_node() -> NodeConfig:
    return create_node_for_state("confirm_envisioned_emotions")

# Create the goodbye node
def create_goodbye_node() -> NodeConfig:
    return create_node_for_state("goodbye")