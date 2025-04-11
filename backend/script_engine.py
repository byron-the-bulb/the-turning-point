class ScriptEngine:
    def __init__(self):
        self.script_stages = {
            "welcome": {
                "text": "Welcome Seeker. To begin your quest, we invite you to ground and center with a few deep breaths.",
                "next": "initial_question",
                "type": "statement"
            },
            "initial_question": {
                "text": "Consider your thoughts. Is there one you wish you could avoid, one that calls for attention but makes you feel stuck, disconnected, or out of balance?",
                "next": "challenge_question",
                "type": "question"
            },
            "challenge_question": {
                "text": "Is there a current challenge you're facing that is associated with that thought?",
                "next": "challenge_states",
                "type": "question"
            },
            "challenge_states": {
                "text": "Which of these challenging states listed on this poster resonate with you at this moment?",
                "next": "recording_intro",
                "type": "selection",
                "options": [
                    "Fearful / Anxious", "Stagnant / Ruminating", "Disassociated / Numb", 
                    "Unhealthy", "Scarcity", "Excluded", "Lack of Control/Agency", 
                    "Disembodied / Ungrounded", "Obsessed", "Silenced / Unheard", 
                    "Lack of Purpose / Unmotivated", "Shameful"
                ]
            },
            "recording_intro": {
                "text": "Please describe what this challenge is like for you. When you are ready to speak your truth, hold your hand out and your guide will start your interactive AI recording sequence.",
                "next": "recording_privacy",
                "type": "instruction"
            },
            "recording_privacy": {
                "text": "Don't worry, these recordings are only for our system – they will not be saved or shared with any person or 3rd party.",
                "next": "recording_challenge",
                "type": "statement"
            },
            "recording_challenge": {
                "text": "Which challenge listed is most alive for you right now?",
                "next": "recording_experience",
                "type": "recording"
            },
            "recording_experience": {
                "text": "What is it like to be going through this?",
                "next": "emotion_reflection",
                "type": "recording"
            },
            "emotion_reflection": {
                "text": "It sounds like you're feeling {emotions} from experiencing {challenge}. Is that true?",
                "next": "emotion_correction",
                "type": "confirmation",
                "yes_next": "transformative_path_suggestion",
                "no_next": "emotion_correction"
            },
            "emotion_correction": {
                "text": "Do any of these words describe your feelings?",
                "next": "transformative_path_suggestion",
                "type": "selection",
                "options": [
                    "Frustrated", "Anxious", "Overwhelmed", "Confused", 
                    "Doubtful", "Fearful", "Stuck", "Resistant",
                    "Purposeless", "Uncertain", "Disappointed", "Disconnected"
                ]
            },
            "transformative_path_suggestion": {
                "text": "Based on your emotions, I suggest the transformative path of {path}. Does this resonate with you?",
                "next": "transformative_path_selection",
                "type": "confirmation",
                "yes_next": "quest_framing",
                "no_next": "transformative_path_selection"
            },
            "transformative_path_selection": {
                "text": "Please select a transformative path from the options provided that resonates with you.",
                "next": "quest_framing",
                "type": "selection",
                "options_from": "challenge_state_paths"
            },
            "quest_framing": {
                "text": "What if your challenges are just the beginning of a quest? What treasures will you gain along the way?",
                "next": "envisioning",
                "type": "question"
            },
            "envisioning": {
                "text": "Envisioning what you seek will help you find your path.",
                "next": "recording_future",
                "type": "statement"
            },
            "recording_future": {
                "text": "When you have passed through this challenge, what will you be like? How will you feel? How will you live your life on the other side of this experience?",
                "next": "future_emotion_reflection",
                "type": "recording"
            },
            "future_emotion_reflection": {
                "text": "It sounds like you will feel {future_emotions}. Is this correct?",
                "next": "future_emotion_correction",
                "type": "confirmation",
                "yes_next": "conclusion",
                "no_next": "future_emotion_correction"
            },
            "future_emotion_correction": {
                "text": "Can you choose one or more states or feelings from this list that you imagine you will experience because you transformed through this challenge?",
                "next": "conclusion",
                "type": "selection",
                "options": [
                    "Creative", "Focused", "Confident", "Peaceful", 
                    "Energized", "Inspired", "Connected", "Purposeful",
                    "Joyful", "Grateful", "Empowered", "Balanced"
                ]
            },
            "conclusion": {
                "text": "Thank you for sharing and taking the time to explore your inner landscape! Now please let your guide know you are ready to view your destiny.",
                "next": "end",
                "type": "statement"
            }
        }
    
    def get_stage(self, stage_name):
        """Get a script stage by name"""
        return self.script_stages.get(stage_name)
    
    def get_next_stage(self, current_stage):
        """Get the next stage after the current one"""
        stage = self.script_stages.get(current_stage)
        if stage and "next" in stage:
            return stage["next"]
        return None
    
    def format_stage_text(self, stage_name, **kwargs):
        """Format the text for a stage with provided variables"""
        stage = self.script_stages.get(stage_name)
        if not stage:
            return ""
        
        text = stage["text"]
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
    
    def get_all_stages(self):
        """Get all script stages"""
        return self.script_stages
