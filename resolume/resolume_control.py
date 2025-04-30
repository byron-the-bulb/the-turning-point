from pythonosc import udp_client
import time
import sys
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, validator, ValidationError
from typing import List, Dict, Optional
import os
from collections import deque

# Resolume OSC settings
RESOLUME_IP = "127.0.0.1"  # Localhost
RESOLUME_PORT = 7000       # Default Resolume OSC port

# Initialize FastAPI app
app = FastAPI()

# Mount templates directory
templates = Jinja2Templates(directory="templates")

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize request queue
request_queue = deque()

# Load video metadata
def load_metadata():
    try:
        with open('video_metadata.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading metadata: {e}")
        return []

# Create OSC client
def create_osc_client():
    try:
        client = udp_client.SimpleUDPClient(RESOLUME_IP, RESOLUME_PORT)
        print(f"OSC client created successfully")
        return client
    except Exception as e:
        print(f"Error creating OSC client: {e}")
        return None

# Input models
class VideoRequest(BaseModel):
    name: str
    challenge_point: str
    envi_state: str
    emotions: Dict[str, float]

class PlayRequest(BaseModel):
    index: int

class VideoItem(BaseModel):
    index: int
    name: str
    challenge_point: str
    envi_state: str
    video: str
    channel: int

    @validator('video')
    def validate_video(cls, v):
        if not v:
            raise ValueError('Video filename is required')
        return v

    @validator('channel')
    def validate_channel(cls, v):
        if v < 1:
            raise ValueError('Channel number must be positive')
        return v

class PlayAllRequest(BaseModel):
    videos: List[VideoItem]

    @validator('videos')
    def validate_videos(cls, v):
        if not v:
            raise ValueError('No videos provided')
        if len(v) > 6:
            raise ValueError('Maximum 6 videos allowed')
        for video in v:
            if video.index < 0 or video.index > 5:
                raise ValueError(f'Invalid slot index: {video.index}. Must be between 0 and 5')
        return v

# Global variables
metadata = load_metadata()
client = create_osc_client()

def find_matching_video(envi_state: str, emotions: Dict[str, float]) -> Optional[str]:
    """
    Find the best matching video based on EnviState and emotions
    """
    best_match = None
    best_score = 0
    
    # Normalize the input envi_state
    input_envi_state = envi_state.lower().strip()
    
    for video in metadata:
        # Normalize the video's envi_state
        video_envi_state = video['EnviState'].lower().strip()
        
        # Check for exact match or contains match
        if input_envi_state == video_envi_state or input_envi_state in video_envi_state or video_envi_state in input_envi_state:
            # Calculate emotion match score
            score = 0
            for emotion, value in emotions.items():
                if emotion in video and video[emotion] != ".":
                    try:
                        video_value = float(video[emotion])
                        score += 1 - abs(video_value - value)
                    except (ValueError, TypeError):
                        continue
            
            if score > best_score:
                best_score = score
                best_match = video['Filename']
    
    print(f"Looking for video matching '{input_envi_state}'")
    if best_match:
        print(f"Found match: {best_match}")
    else:
        print("No match found")
    
    return best_match

def set_text_overlay(text: str, layer: int):
    """
    Set text overlay in Resolume for a specific layer
    """
    if not client:
        raise HTTPException(status_code=500, detail="OSC client not initialized")
    
    try:
        # Set the text content using the correct address
        message = f"/composition/layers/{layer}/video/effects/text/params/lines"
        print(f"Sending OSC message: {message} with value: {text}")
        client.send_message(message, text)
        
        print(f"Successfully set text overlay for layer {layer}: {text}")
    except Exception as e:
        print(f"Error setting text overlay: {e}")
        raise HTTPException(status_code=500, detail=f"Error setting text overlay: {e}")

def trigger_video(filename: str, name: str, challenge_point: str, envi_state: str, layer: int, channel: int):
    """
    Trigger a video in Resolume based on filename and set text overlay
    Assumes the layer layout is already set up in Resolume
    """
    if not client:
        raise HTTPException(status_code=500, detail="OSC client not initialized")
    
    try:
        # Set text overlay
        text = f"{name} - {challenge_point} to {envi_state}"
        set_text_overlay(text, layer)
        
        # Trigger the video
        message = f"/composition/layers/{layer}/clips/{channel}/connect"
        print(f"Sending OSC message: {message} with value: 1")
        client.send_message(message, 1)  # Send value 1 to trigger the clip
        print(f"Successfully triggered video {filename} on layer {layer}")
    except Exception as e:
        print(f"Error sending OSC message: {e}")
        raise HTTPException(status_code=500, detail=f"Error sending OSC message: {e}")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/trigger_video")
async def trigger_video_endpoint(request: VideoRequest):
    """
    Endpoint to add a video request to the queue or first available slot
    """
    # Find matching video
    matching_video = find_matching_video(request.envi_state, request.emotions)
    
    if not matching_video:
        raise HTTPException(status_code=404, detail="No matching video found")
    
    # Find the channel number based on alphabetical order
    sorted_files = sorted([v['Filename'] for v in metadata])
    try:
        channel = sorted_files.index(matching_video) + 1  # +1 because Resolume channels start at 1
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Video {matching_video} not found in metadata")
    
    # Create the request object
    request_data = {
        "name": request.name,
        "challenge_point": request.challenge_point,
        "envi_state": request.envi_state,
        "video": matching_video,
        "channel": channel
    }
    
    # Add request to queue
    request_queue.append(request_data)
    
    return {
        "status": "success",
        "message": "Request added to queue",
        "queue_position": len(request_queue),
        "video": matching_video,
        "channel": channel
    }

@app.get("/queue")
async def get_queue():
    """
    Get the current request queue
    """
    return list(request_queue)

@app.post("/play-all")
async def play_all_videos(request: PlayAllRequest):
    """
    Play multiple videos in different layers with a 5-second interval
    """
    try:
        print(f"Received request to play {len(request.videos)} videos")
        for i, video in enumerate(request.videos):
            print(f"\nProcessing video {i+1}:")
            print(f"Name: {video.name}")
            print(f"Challenge Point: {video.challenge_point}")
            print(f"Envi State: {video.envi_state}")
            print(f"Video: {video.video}")
            print(f"Channel: {video.channel}")
            print(f"Layer: {video.index + 1}")
            
            # Trigger video in the specified layer
            trigger_video(
                video.video,
                video.name,
                video.challenge_point,
                video.envi_state,
                video.index + 1,  # Layer numbers start at 1
                video.channel
            )
            # Wait 5 seconds before triggering the next video
            if i < len(request.videos) - 1:  # Don't wait after the last video
                print("Waiting 5 seconds before next video...")
                time.sleep(5)
        
        return {
            "status": "success",
            "message": "All videos triggered successfully"
        }
    except ValidationError as e:
        print(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        print(f"Error in play_all_videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 