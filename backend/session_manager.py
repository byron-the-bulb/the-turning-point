import uuid
import json
import time
from datetime import datetime

class SessionManager:
    def __init__(self, storage_path="./sessions"):
        self.storage_path = storage_path
        self.active_sessions = {}
        
    def create_session(self):
        """Create a new session and return session ID"""
        session_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        session_data = {
            "id": session_id,
            "created_at": timestamp,
            "updated_at": timestamp,
            "status": "created",
            "recordings": {},
            "emotions": {},
            "script_stage": "welcome",
            "challenge_state": None,
            "transformative_path": None,
            "emotional_footprint": None
        }
        
        self.active_sessions[session_id] = session_data
        self._save_session(session_id)
        
        return session_id
    
    def update_session(self, session_id, updates):
        """Update session data"""
        if session_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[session_id]
        session.update(updates)
        session["updated_at"] = datetime.now().isoformat()
        
        self._save_session(session_id)
        return True
    
    def get_session(self, session_id):
        """Get session data"""
        return self.active_sessions.get(session_id)
    
    def end_session(self, session_id):
        """End a session and archive it"""
        if session_id not in self.active_sessions:
            return False
        
        session = self.active_sessions[session_id]
        session["status"] = "completed"
        session["completed_at"] = datetime.now().isoformat()
        
        self._save_session(session_id)
        del self.active_sessions[session_id]
        
        return True
    
    def _save_session(self, session_id):
        """Save session data to storage"""
        import os
        os.makedirs(self.storage_path, exist_ok=True)
        
        session = self.active_sessions[session_id]
        filename = f"{self.storage_path}/{session_id}.json"
        
        with open(filename, "w") as f:
            json.dump(session, f, indent=2)
