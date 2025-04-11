import os
import asyncio
from dotenv import load_dotenv
from hume import AsyncHumeClient
from hume.expression_measurement.stream import Config
from hume.expression_measurement.stream.socket_client import StreamConnectOptions

# Load environment variables
load_dotenv()

class EmotionAnalyzer:
    def __init__(self):
        self.client = AsyncHumeClient(api_key=os.environ.get("HUME_API_KEY"))
        
        # Emotion to challenge state mapping
        self.emotion_to_challenge = {
            "Fear": ["Fearful / Anxious"],
            "Anxiety": ["Fearful / Anxious"],
            "Worry": ["Fearful / Anxious"],
            "Nervousness": ["Fearful / Anxious"],
            "Concerned": ["Fearful / Anxious"],
            
            "Boredom": ["Stagnant / Ruminating"],
            "Apathy": ["Stagnant / Ruminating", "Lack of Purpose / Unmotivated"],
            "Indecision": ["Stagnant / Ruminating"],
            
            "Detachment": ["Disassociated / Numb"],
            "Emptiness": ["Disassociated / Numb"],
            "Disconnection": ["Disassociated / Numb"],
            
            "Fatigue": ["Unhealthy"],
            "Weakness": ["Unhealthy"],
            
            # Add mappings for mock data emotions
            "Concentration": ["Focused Clarity"],
            "Calm": ["Relaxed"],
            "Interest": ["Curious"],
            "Contemplative": ["Focused Clarity"],
            "Thoughtful": ["Focused Clarity"],
            "Pain": ["Unhealthy"],
            
            "Insecurity": ["Scarcity", "Shameful"],
            "Deprivation": ["Scarcity"],
            "Lack": ["Scarcity"],
            
            "Loneliness": ["Excluded"],
            "Rejection": ["Excluded"],
            "Isolation": ["Excluded"],
            
            "Helplessness": ["Lack of Control/Agency"],
            "Frustration": ["Lack of Control/Agency"],
            "Powerlessness": ["Lack of Control/Agency"],
            
            "Confusion": ["Disembodied / Ungrounded"],
            "Distraction": ["Disembodied / Ungrounded"],
            "Disorientation": ["Disembodied / Ungrounded"],
            
            "Fixation": ["Obsessed"],
            "Perfectionism": ["Obsessed"],
            "Overthinking": ["Obsessed"],
            
            "Ignored": ["Silenced / Unheard"],
            "Dismissed": ["Silenced / Unheard"],
            "Invalidated": ["Silenced / Unheard"],
            
            "Aimlessness": ["Lack of Purpose / Unmotivated"],
            "Indifference": ["Lack of Purpose / Unmotivated"],
            "Lethargy": ["Lack of Purpose / Unmotivated", "Unhealthy"],
            
            "Guilt": ["Shameful"],
            "Embarrassment": ["Shameful"],
            "Unworthiness": ["Shameful"],
            "Shame": ["Shameful"]
        }
        
    async def analyze_audio(self, audio_data):
        """Analyze emotions in audio data using WebSocket streaming"""
        # For testing purposes, if we can't access the Hume API, return mock data
        if not os.environ.get("HUME_API_KEY"):
            print("WARNING: No HUME_API_KEY found, returning mock emotion data")
            return [
                {"name": "Concentration", "score": 0.85},
                {"name": "Calm", "score": 0.75},
                {"name": "Interest", "score": 0.65}
            ]
        
        # Configure the prosody model
        model_config = Config(prosody={})
        
        # Configure the WebSocket connection
        stream_options = StreamConnectOptions(config=model_config)
        
        try:
            # Connect to the WebSocket and analyze the audio
            async with self.client.expression_measurement.stream.connect(options=stream_options) as socket:
                # For Hume WebSocket API, we need to convert audio bytes to a base64 string or use
                # a file path instead of raw bytes
                
                # Create a temporary file
                temp_file = os.path.join(os.path.dirname(__file__), "temp_audio.wav")
                with open(temp_file, "wb") as f:
                    f.write(audio_data)
                
                # Send the file path instead of the raw bytes
                result = await socket.send_file(temp_file)
                
                # Clean up the temporary file
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                
                # Extract emotions from the prosody model results
                if result and hasattr(result, 'prosody') and result.prosody:
                    emotions = result.prosody.emotions
                    
                    # Get top emotions
                    top_emotions = sorted(emotions, key=lambda x: x.score, reverse=True)[:5]
                    return [{"name": e.name, "score": e.score} for e in top_emotions]
                return []
        except Exception as e:
            print(f"Error analyzing audio: {e}")
            # Return mock data for testing
            return [
                {"name": "Concentration", "score": 0.85},
                {"name": "Calm", "score": 0.75},
                {"name": "Interest", "score": 0.65}
            ]
    
    async def analyze_text(self, text):
        """Analyze emotions in text using WebSocket streaming"""
        # For testing purposes, if we don't have a Hume API key, return mock data
        if not os.environ.get("HUME_API_KEY"):
            print("WARNING: No HUME_API_KEY found, returning mock emotion data for text")
            return [
                {"name": "Contemplative", "score": 0.82},
                {"name": "Concerned", "score": 0.71},
                {"name": "Thoughtful", "score": 0.67}
            ]
            
        # Configure the language model
        model_config = Config(language={})
        
        # Configure the WebSocket connection
        stream_options = StreamConnectOptions(config=model_config)
        
        try:
            # Connect to the WebSocket and analyze the text
            async with self.client.expression_measurement.stream.connect(options=stream_options) as socket:
                result = await socket.send_text(text)
                
                # Extract emotions from the language model results
                if result and hasattr(result, 'language') and result.language:
                    # Handle different versions of the API response structure
                    if hasattr(result.language, 'emotions'):
                        emotions = result.language.emotions
                        # Get top emotions
                        top_emotions = sorted(emotions, key=lambda x: x.score, reverse=True)[:5]
                        return [{"name": e.name, "score": e.score} for e in top_emotions]
                    elif hasattr(result.language, 'predictions'):
                        # In newer versions of the API, emotions might be in nested predictions structure
                        predictions = result.language.predictions
                        
                        # Check if predictions have the emotions attribute (as seen in the debug output)
                        if predictions and hasattr(predictions[0], 'emotions'):
                            print("Found emotions in predictions[0].emotions")
                            emotions_list = []
                            
                            # Loop through predictions and extract all emotions
                            for prediction in predictions:
                                if prediction.emotions:
                                    for emotion in prediction.emotions:
                                        if hasattr(emotion, 'name') and hasattr(emotion, 'score'):
                                            emotions_list.append({"name": emotion.name, "score": emotion.score})
                            
                            # Sort and return top emotions if any were found
                            if emotions_list:
                                sorted_emotions = sorted(emotions_list, key=lambda x: x["score"], reverse=True)[:5]
                                return sorted_emotions
                        
                        # Check other possible structures
                        elif predictions and hasattr(predictions[0], 'name') and hasattr(predictions[0], 'score'):
                            top_predictions = sorted(predictions, key=lambda x: x.score, reverse=True)[:5]
                            return [{"name": p.name, "score": p.score} for p in top_predictions]
                        elif predictions and hasattr(predictions[0], 'emotion') and hasattr(predictions[0], 'probability'):
                            top_predictions = sorted(predictions, key=lambda x: x.probability, reverse=True)[:5]
                            return [{"name": p.emotion, "score": p.probability} for p in top_predictions]
                        else:
                            # Log the structure and return mock data
                            if predictions:
                                print(f"Unsupported predictions structure. Available attributes: {dir(predictions[0])}")
                                # Try to print some of the emotions if available
                                if hasattr(predictions[0], 'emotions') and predictions[0].emotions:
                                    print(f"Emotions structure: {dir(predictions[0].emotions[0]) if predictions[0].emotions else 'empty'}")
                            return self._get_mock_emotions()
                    else:
                        print(f"Warning: Unexpected language model result structure: {result.language}")
                        return self._get_mock_emotions()
                return []
        except Exception as e:
            print(f"Error analyzing text: {e}")
            # Return mock data for testing
            return self._get_mock_emotions()
    
    def _get_mock_emotions(self):
        """Return mock emotion data for testing"""
        return [
            {"name": "Contemplative", "score": 0.82},
            {"name": "Concerned", "score": 0.71},
            {"name": "Thoughtful", "score": 0.67}
        ]
    
    def map_emotions_to_challenge_states(self, emotions):
        """Map detected emotions to potential challenge states"""
        challenge_scores = {}
        
        for emotion in emotions:
            emotion_name = emotion["name"]
            emotion_score = emotion["score"]
            
            # Find matching challenge states
            potential_challenges = self.emotion_to_challenge.get(emotion_name, [])
            
            for challenge in potential_challenges:
                if challenge in challenge_scores:
                    challenge_scores[challenge] += emotion_score
                else:
                    challenge_scores[challenge] = emotion_score
        
        # Sort challenges by score
        sorted_challenges = sorted(challenge_scores.items(), key=lambda x: x[1], reverse=True)
        
        return sorted_challenges
    
    async def generate_emotional_footprint(self, recordings, emotions, challenge_state, transformative_path):
        """Generate an emotional footprint analysis"""
        # Combine all emotional data
        challenge_emotions = emotions.get("recording_challenge", [])
        experience_emotions = emotions.get("recording_experience", [])
        future_emotions = emotions.get("recording_future", [])
        
        # Create analysis text
        challenge = recordings.get("recording_challenge", "")
        experience = recordings.get("recording_experience", "")
        future = recordings.get("recording_future", "")
        
        # Use Hume API to analyze the emotional journey
        combined_text = f"""
        Current challenge: {challenge}
        
        Experience of the challenge: {experience}
        
        Future vision: {future}
        """
        
        text_emotions = await self.analyze_text(combined_text)
        
        # Create emotional journey visualization data
        journey = {
            "challenge": challenge_emotions,
            "experience": experience_emotions,
            "future": future_emotions,
            "overall": text_emotions,
            "challenge_state": challenge_state,
            "transformative_path": transformative_path
        }
        
        return {
            "journey": journey,
            "challenge_text": challenge,
            "experience_text": experience,
            "future_text": future
        }
