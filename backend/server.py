import os
import json
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.frames.frames import InputAudioRawFrame, LLMTextFrame, TTSSpeakFrame

# Import custom modules
from .transformative_paths import TransformativePathSelector
from .emotion_analyzer import EmotionAnalyzer

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Use the emotion analyzer we've already updated
from hume import AsyncHumeClient

# Initialize emotion analyzer and transformative path selector
emotion_analyzer = EmotionAnalyzer()
path_selector = TransformativePathSelector()

# Script stages and prompts
SCRIPT_STAGES = {
    "welcome": "Welcome Seeker. To begin your quest, we invite you to ground and center with a few deep breaths.",
    "initial_question": "Consider your thoughts. Is there one you wish you could avoid, one that calls for attention but makes you feel stuck, disconnected, or out of balance?",
    "challenge_question": "Is there a current challenge you're facing that is associated with that thought?",
    "challenge_states": "Which of these challenging states listed on this poster resonate with you at this moment?",
    "recording_intro": "Please describe what this challenge is like for you. When you are ready to speak your truth, hold your hand out and your guide will start your interactive AI recording sequence.",
    "recording_privacy": "Don't worry, these recordings are only for our system – they will not be saved or shared with any person or 3rd party.",
    "recording_challenge": "Which challenge listed is most alive for you right now?",
    "recording_experience": "What is it like to be going through this?",
    "emotion_reflection": "It sounds like you're feeling {emotions} from experiencing {challenge}. Is that true?",
    "emotion_correction": "Do any of these words describe your feelings?",
    "transformative_path_suggestion": "Based on your emotions, I suggest the transformative path of {path}. Does this resonate with you?",
    "transformative_path_selection": "Please select a transformative path from the options provided that resonates with you.",
    "quest_framing": "What if your challenges are just the beginning of a quest? What treasures will you gain along the way?",
    "envisioning": "Envisioning what you seek will help you find your path.",
    "recording_future": "When you have passed through this challenge, what will you be like? How will you feel? How will you live your life on the other side of this experience?",
    "future_emotion_reflection": "It sounds like you will feel {future_emotions}. Is this correct?",
    "future_emotion_correction": "Can you choose one or more states or feelings from this list that you imagine you will experience because you transformed through this challenge?",
    "conclusion": "Thank you for sharing and taking the time to explore your inner landscape! Now please let your guide know you are ready to view your destiny."
}

# Challenge states and their transformative paths
CHALLENGE_STATES = {
    "Fearful / Anxious": ["Confident", "Experimental / Risking", "Courageous", "Leadership"],
    "Stagnant / Ruminating": ["Experimental / Risking", "Spontaneous / Decisive", "Enthusiastic"],
    "Disassociated / Numb": ["Engaged", "Curious", "Feeling / Empathetic"],
    "Unhealthy": ["Full Capacity", "Energetic", "Honoring Body"],
    "Scarcity": ["Generous", "Having/Abundance", "Indulging in Pleasure", "Investing", "Experimental / Risking"],
    "Excluded": ["Belonging", "Respected", "Trusting Others", "Leadership", "Receiving"],
    "Lack of Control/Agency": ["Experimental / Risking", "Accepting Change", "Trusting Others", "Leadership", "Relaxed"],
    "Disembodied / Ungrounded": ["Honoring Body", "Joyful Physical Expression", "Focused Clarity", "Enthusiastic"],
    "Obsessed": ["Relaxed", "Accepting Change", "Experimental"],
    "Silenced / Unheard": ["Leadership", "Confident", "Receiving"],
    "Lack of Purpose / Unmotivated": ["Enthusiastic", "Leadership", "Focused Clarity"],
    "Shameful": ["Self-Love / Pride", "Leadership", "Confident", "Honoring Body"]
}

# Active sessions
sessions = {}

# We'll use the updated EmotionAnalyzer class for emotion analysis
# Removed the redundant analyze_emotions function

# Create Pipecat pipeline using the latest pattern
def create_pipeline(session_id):
    """Create a new Pipecat pipeline for a session"""
    # Configure components
    whisper = WhisperSTTService(model="whisper-1")
    llm = OpenAILLMService(
        model="gpt-4o",
        system_prompt=f"""You are Sphinx, an AI guide for an interactive art installation. 
        Follow the script exactly, but respond naturally to the participant's inputs.
        Analyze their emotional state based on their responses.
        Current session ID: {session_id}"""
    )
    tts = CartesiaTTSService(
        api_key=os.environ.get("CARTESIA_API_KEY"),
        voice_id="f114a467-c40a-4db8-964d-aaba89cd08fa"
    )
    
    # Create pipeline with components
    pipeline = Pipeline([
        whisper,
        llm,
        tts
    ])
    
    return pipeline

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    
    # Create new session if it doesn't exist
    if session_id not in sessions:
        sessions[session_id] = {
            "stage": "welcome",
            "recordings": {},
            "emotions": {},
            "challenge": None,
            "challenge_state": None,
            "transformative_path": None,
            "future_state": None
        }
    
    session = sessions[session_id]
    
    # With the latest Pipecat SDK, we create pipelines as needed for each task
    # instead of reusing a single pipeline
    
    try:
        while True:
            data = await websocket.receive_json()
            command = data.get("command")
            
            if command == "start_session":
                # Send welcome message
                await websocket.send_json({
                    "type": "script",
                    "stage": "welcome",
                    "text": SCRIPT_STAGES["welcome"]
                })
                session["stage"] = "initial_question"
                
            elif command == "next_stage":
                current_stage = session["stage"]
                # Progress through script stages
                if current_stage in SCRIPT_STAGES:
                    await websocket.send_json({
                        "type": "script",
                        "stage": current_stage,
                        "text": SCRIPT_STAGES[current_stage]
                    })
                    
                    # Update stage
                    stages = list(SCRIPT_STAGES.keys())
                    current_index = stages.index(current_stage)
                    if current_index < len(stages) - 1:
                        session["stage"] = stages[current_index + 1]
            
            elif command == "start_recording":
                # Start audio recording - with the latest SDK, we'd use a microphone source
                # For now, we'll just notify that recording has started
                await websocket.send_json({"type": "recording_started"})
                
            elif command == "stop_recording":
                # In the latest SDK, we'd use a PipelineRunner to process the recording
                # For now, we'll use the audio data sent from the client
                audio_data = data.get("audio_data")
                if not audio_data:
                    await websocket.send_json({"type": "error", "message": "No audio data received"})
                    continue
                
                # Create a runner and task for transcription
                runner = PipelineRunner()
                pipeline = Pipeline([WhisperSTTService(model="medium")])
                task = PipelineTask(pipeline)
                
                # Queue the audio for transcription - use InputAudioRawFrame for Pipecat 0.0.62
                # Include required sample_rate and num_channels parameters
                await task.queue_frames([InputAudioRawFrame(
                    audio_data, 
                    sample_rate=16000,  # Assuming 16kHz audio
                    num_channels=1      # Assuming mono audio
                )])
                result = await runner.run(task)
                transcription = result.text if result else ""
                
                # Store recording
                current_stage = session["stage"]
                session["recordings"][current_stage] = transcription
                
                # Analyze emotions if this is a key recording
                if current_stage in ["recording_challenge", "recording_experience", "recording_future"]:
                    # Use the updated EmotionAnalyzer class
                    emotions = await emotion_analyzer.analyze_audio(audio_data)
                    session["emotions"][current_stage] = emotions
                    
                    # Store challenge or future state
                    if current_stage == "recording_challenge":
                        session["challenge"] = transcription
                        
                        # Determine challenge state based on emotions and transcription
                        challenge_state = await path_selector.determine_challenge_state(
                            emotions, 
                            transcription
                        )
                        session["challenge_state"] = challenge_state
                        
                    elif current_stage == "recording_future":
                        session["future_state"] = transcription
                
                await websocket.send_json({
                    "type": "transcription",
                    "text": transcription,
                    "emotions": session["emotions"].get(current_stage, [])
                })
                
                # If we just processed the recording_experience, suggest a transformative path
                if current_stage == "recording_experience":
                    # Get challenge state
                    challenge_state = session["challenge_state"]
                    
                    # Select transformative path
                    if challenge_state:
                        transformative_path = await path_selector.select_path(
                            challenge_state,
                            session["emotions"].get("recording_challenge", []),
                            session["emotions"].get("recording_experience", []),
                            session["recordings"].get("recording_challenge", ""),
                            session["recordings"].get("recording_experience", "")
                        )
                        
                        session["transformative_path"] = transformative_path
                        
                        # Send transformative path suggestion
                        await websocket.send_json({
                            "type": "transformative_path",
                            "challenge_state": challenge_state,
                            "path": transformative_path,
                            "all_paths": CHALLENGE_STATES.get(challenge_state, [])
                        })
                
            elif command == "generate_response":
                # Generate LLM response based on current stage
                current_stage = session["stage"]
                user_input = data.get("text", "")
                
                # Format prompt based on stage
                if current_stage == "emotion_reflection":
                    # Get top emotions from recording_experience
                    emotions = session["emotions"].get("recording_experience", [])
                    emotion_names = ", ".join([e["name"] for e in emotions[:2]])
                    challenge = session["challenge"]
                    prompt = SCRIPT_STAGES[current_stage].format(emotions=emotion_names, challenge=challenge)
                elif current_stage == "transformative_path_suggestion":
                    # Use selected transformative path
                    path = session["transformative_path"]
                    prompt = SCRIPT_STAGES[current_stage].format(path=path)
                elif current_stage == "future_emotion_reflection":
                    # Predict positive emotions for future state
                    prompt = SCRIPT_STAGES[current_stage].format(future_emotions="creative and focused")
                else:
                    prompt = SCRIPT_STAGES.get(current_stage, "")
                
                # Create a pipeline for generating response and audio
                runner = PipelineRunner()
                
                # Set up LLM and TTS pipeline
                llm = OpenAILLMService(model="gpt-4o")
                tts = CartesiaTTSService(
                    api_key=os.environ.get("CARTESIA_API_KEY"),
                    voice_id="f114a467-c40a-4db8-964d-aaba89cd08fa"
                )
                
                # Create pipeline and task
                pipeline = Pipeline([llm, tts])
                task = PipelineTask(pipeline)
                
                # Queue the prompt for processing - use LLMTextFrame for Pipecat 0.0.62
                await task.queue_frames([LLMTextFrame(prompt)])
                result = await runner.run(task)
                
                # Extract response and audio
                response = result.text if hasattr(result, 'text') else ""
                audio = result.audio if hasattr(result, 'audio') else None
                
                # Send response
                await websocket.send_json({
                    "type": "response",
                    "text": response,
                    "audio_url": audio.url if hasattr(audio, "url") else None
                })
                
            elif command == "select_transformative_path":
                # User selects a transformative path
                selected_path = data.get("path")
                if selected_path:
                    session["transformative_path"] = selected_path
                    
                    await websocket.send_json({
                        "type": "path_selected",
                        "path": selected_path
                    })
                    
                    # Move to next stage
                    session["stage"] = "quest_framing"
                
            elif command == "generate_emotional_footprint":
                # Generate emotional footprint analysis
                challenge_emotions = session["emotions"].get("recording_challenge", [])
                experience_emotions = session["emotions"].get("recording_experience", [])
                future_emotions = session["emotions"].get("recording_future", [])
                
                challenge_state = session["challenge_state"]
                transformative_path = session["transformative_path"]
                
                # Combine all emotions for analysis
                all_emotions = {
                    "challenge": challenge_emotions,
                    "experience": experience_emotions,
                    "future": future_emotions
                }
                
                # Generate emotional journey narrative
                prompt = f"""
                Based on the participant's emotional journey:
                
                Current challenge emotions: {challenge_emotions}
                Current experience emotions: {experience_emotions}
                Future state emotions: {future_emotions}
                
                Challenge state: {challenge_state}
                Transformative path: {transformative_path}
                
                Create a brief emotional footprint analysis that highlights their transformation journey 
                from their current challenge state to their future state via their chosen transformative path.
                """
                
                # Create a pipeline runner and task for generating the analysis
                runner = PipelineRunner()
                llm = OpenAILLMService(model="gpt-4o")
                pipeline = Pipeline([llm])
                task = PipelineTask(pipeline)
                
                # Queue the prompt for processing - use LLMTextFrame for Pipecat 0.0.62
                await task.queue_frames([LLMTextFrame(prompt)])
                result = await runner.run(task)
                
                # Extract analysis
                analysis = result.text if hasattr(result, 'text') else ""
                
                await websocket.send_json({
                    "type": "emotional_footprint",
                    "analysis": analysis,
                    "emotions": all_emotions,
                    "challenge_state": challenge_state,
                    "transformative_path": transformative_path
                })
                
            elif command == "end_session":
                # Clean up session
                if session_id in sessions:
                    del sessions[session_id]
                await websocket.send_json({"type": "session_ended"})
                break
                
    except WebSocketDisconnect:
        # Clean up on disconnect
        if session_id in sessions:
            del sessions[session_id]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
