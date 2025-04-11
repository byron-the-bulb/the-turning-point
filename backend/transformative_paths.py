import json
import os
import random
from .emotion_analyzer import EmotionAnalyzer

class TransformativePathSelector:
    def __init__(self, data_path="./data"):
        self.data_path = data_path
        self.emotion_analyzer = EmotionAnalyzer()
        
        # Load challenge states and transformative paths
        self.challenge_states = {
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
        
        # Save challenge states to file
        self._save_challenge_states()
    
    def _save_challenge_states(self):
        """Save challenge states and transformative paths to file"""
        os.makedirs(self.data_path, exist_ok=True)
        
        with open(f"{self.data_path}/challenge_states.json", "w") as f:
            json.dump(self.challenge_states, f, indent=2)
    
    async def determine_challenge_state(self, emotions, transcription):
        """Determine the most likely challenge state based on emotions and transcription"""
        # Check if emotions is None or empty
        if not emotions:
            emotions = []
            
        # Map emotions to challenge states
        challenge_candidates = self.emotion_analyzer.map_emotions_to_challenge_states(emotions)
        
        # If we have candidates, return the top one
        if challenge_candidates:
            return challenge_candidates[0][0]
        
        # Fallback: analyze the transcription text if we have it
        if transcription and transcription.strip():
            text_emotions = await self.emotion_analyzer.analyze_text(transcription)
            text_challenge_candidates = self.emotion_analyzer.map_emotions_to_challenge_states(text_emotions)
            
            if text_challenge_candidates:
                return text_challenge_candidates[0][0]
                
        # Default fallback if no challenge state could be determined
        return "Focused Clarity"
        
        # If still no match, return a random challenge state
        return random.choice(list(self.challenge_states.keys()))
    
    async def select_path(self, challenge_state, challenge_emotions, experience_emotions, challenge_text, experience_text):
        """Select the most appropriate transformative path for the challenge state"""
        # Get available paths for this challenge state
        available_paths = self.challenge_states.get(challenge_state, [])
        
        if not available_paths:
            # Fallback if challenge state not found
            return "Confident"
        
        # For now, select the first path (most common/recommended)
        # In a more advanced implementation, this could use LLM to select the most appropriate path
        # based on the specific emotions and text content
        return available_paths[0]
    
    def get_all_paths_for_challenge(self, challenge_state):
        """Get all transformative paths for a given challenge state"""
        return self.challenge_states.get(challenge_state, [])
