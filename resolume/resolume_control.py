from pythonosc import udp_client
import time
import sys
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, validator, ValidationError, Field
from typing import List, Dict, Optional, Union
import os
from collections import deque
import asyncio

# Resolume OSC settings
RESOLUME_IP = "192.168.1.187"  # Localhost
RESOLUME_PORT = 7000       # Default Resolume OSC port

# Initialize FastAPI app
app = FastAPI()

# Mount templates directory
templates = Jinja2Templates(directory="templates")

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize request queue
request_queue = deque()

# Global task tracker for the play_video_sequence
current_play_task = None

# Load video metadata
def load_metadata():
    try:
        with open('video_metadata.json', 'r') as f:
            data = json.load(f)
            print(f"Loaded {len(data)} videos from metadata file")
            return data
    except FileNotFoundError:
        print("Warning: video_metadata.json not found. Creating a basic version.")
        
        # Create a basic metadata file with one entry for each empowered state
        empowered_states = [
            "Confident", "Risking", "Leadership", "Spontaneous", "Enthusiastic",
            "Engaged", "Curious", "Empathetic", "Full Capacity", "Energetic",
            "Honoring Body", "Indulging In Pleasure", "Investing", "Respected",
            "Trusting Others", "Recieving", "Communing", "Accepting Change", "Relaxed",
            "Joyful Physical Expression", "Focused Clarity", "Experimental", "Self-Love"
        ]
        
        basic_metadata = []
        for i, state in enumerate(empowered_states):
            basic_metadata.append({
                "Filename": f"video_{i+1}.mp4",
                "EnviState": state,
                "joy": "0.5",
                "fear": "0.5",
                "anger": "0.5",
                "sadness": "0.5",
                "trust": "0.5"
            })
        
        # Save the basic metadata file
        try:
            with open('video_metadata.json', 'w') as f:
                json.dump(basic_metadata, f, indent=2)
            print(f"Created basic metadata file with {len(basic_metadata)} entries")
            return basic_metadata
        except Exception as e:
            print(f"Error creating basic metadata file: {e}")
            return []
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
class EmotionItem(BaseModel):
    name: str
    score: float

class VideoRequest(BaseModel):
    name: str
    challenge_point: str
    envi_state: str
    emotions: Union[Dict[str, float], List[EmotionItem]]

class ManualEntryRequest(BaseModel):
    name: str
    challenge_point: str
    envi_state: str

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

class HelpRequest(BaseModel):
    user: str = Field(..., description="The name of the user or stage requiring assistance (e.g., 'Greeting', 'Name collection', etc.)")
    needs_help: bool = Field(..., description="Set to true to request help, false to cancel help request")

class BurnerData(BaseModel):
    name: str
    challenge_point: str
    envi_state: str

class BurnersToRemoveRequest(BaseModel):
    burners_to_remove: List[BurnerData] = Field(default=[], description="List of burner data to remove from the queue")

# Global variables
metadata = load_metadata()
client = create_osc_client()
help_needed = False  # Track help state
help_user = ""  # Track who needs help

def find_matching_video(envi_state: str, emotions: Dict[str, float]) -> Optional[str]:
    """
    Find the best matching video based on EnviState and emotions
    """
    best_match = None
    best_score = 0
    fallback_match = None  # Added fallback match for when emotion matching fails
    
    # Normalize the input envi_state
    input_envi_state = envi_state.lower().strip()
    
    for video in metadata:
        # Normalize the video's envi_state
        video_envi_state = video['EnviState'].lower().strip()
        
        # Check for exact match or contains match
        if input_envi_state == video_envi_state or input_envi_state in video_envi_state or video_envi_state in input_envi_state:
            # Store as fallback match - will use this if no emotion match is found
            if fallback_match is None:
                fallback_match = video['Filename']
                
            # Calculate emotion match score
            score = 0
            emotions_found = False
            for emotion, value in emotions.items():
                if emotion in video and video[emotion] != ".":
                    try:
                        video_value = float(video[emotion])
                        score += 1 - abs(video_value - value)
                        emotions_found = True
                    except (ValueError, TypeError):
                        continue
            
            # Only update best match if we actually found emotions to match with
            if emotions_found and score > best_score:
                best_score = score
                best_match = video['Filename']
    
    # Use fallback match if no emotion-based match was found
    if best_match is None and fallback_match is not None:
        best_match = fallback_match
        print(f"Using fallback match for '{input_envi_state}': {best_match}")
    else:
        print(f"Looking for video matching '{input_envi_state}'")
        if best_match:
            print(f"Found match: {best_match}")
        else:
            print("No match found")
    
    return best_match

def set_text_overlay(text: str, layer: int):
    """
    Set text overlay in Resolume for a specific layer/group
    
    Layer mapping:
    Layer 1: composition 
    Layer 2: square/group 1
    Layer 3: Group 3
    Layer 4: Group 4 
    etc.
    """
    if not client:
        raise HTTPException(status_code=500, detail="OSC client not initialized")
    
    try:
        # Use the correct address format for groups - ONLY FOR TEXT OVERLAYS
        if layer == 1:
            # Special case for composition layer
            message = f"/composition/video/effects/textblock/effect/text/params/lines"
        elif layer == 2:
            # Updated addressing for square/layer 2 - use group 1 addressing
            message = f"/composition/groups/2/video/effects/textblock/effect/text/params/lines"
        else:
            # For layers 3 and above, they correspond to group numbers
            message = f"/composition/groups/{layer}/video/effects/textblock/effect/text/params/lines"
            
        print(f"Sending OSC message: {message} with value: {text}")
        client.send_message(message, text)
        
        print(f"Successfully set text overlay for layer/group {layer}: {text}")
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
        
        # Add +1 to the channel to account for empty first column
        adjusted_channel = channel + 1
        
        # IMPORTANT: Always use the original layer-based addressing for clips
        message = f"/composition/layers/{layer}/clips/{adjusted_channel}/connect"
            
        print(f"Sending OSC message: {message} with value: 1 (adjusted from channel {channel})")
        client.send_message(message, 1)  # Send value 1 to trigger the clip
        print(f"Successfully triggered video {filename} on layer {layer}, channel {adjusted_channel}")
    except Exception as e:
        print(f"Error sending OSC message: {e}")
        raise HTTPException(status_code=500, detail=f"Error sending OSC message: {e}")

def toggle_layer(layer: int, on: bool = True):
    """
    Turn a layer on or off in Resolume
    
    If on=False, triggers the empty clip in column 1 to effectively stop the layer
    """
    if not client:
        raise HTTPException(status_code=500, detail="OSC client not initialized")
    
    try:
        if on:
            # Turn on the layer
            message = f"/composition/layers/{layer}/connect"
            value = 1
            print(f"Sending OSC message: {message} with value: {value}")
            client.send_message(message, value)
            print(f"Successfully activated layer {layer}")
        else:
            # To stop/clear a layer, trigger the empty clip in column 1
            message = f"/composition/layers/{layer}/clips/1/connect"
            value = 1
            print(f"Sending OSC message: {message} with value: {value} (to clear the layer)")
            client.send_message(message, value)
            print(f"Successfully cleared layer {layer} by triggering empty column 1")
    except Exception as e:
        print(f"Error toggling layer: {e}")
        raise HTTPException(status_code=500, detail=f"Error toggling layer: {e}")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/help", response_class=HTMLResponse)
async def help_monitor(request: Request):
    """
    Display the Help Status Monitor page
    """
    return templates.TemplateResponse("help_status.html", {"request": request})

@app.get("/manual_entry", response_class=HTMLResponse)
async def manual_entry_page(request: Request):
    """
    Display the Manual Entry page for manually entering participant data
    """
    return templates.TemplateResponse("manual_entry.html", {"request": request})

@app.post("/manual_entry")
async def manual_entry(request: ManualEntryRequest):
    """
    Endpoint to manually add a participant to the queue without going through the Sphinx API
    """
    print(f"Manual entry received: {request}")
    
    # Debug: Print metadata structure
    print(f"Metadata count: {len(metadata)}")
    if len(metadata) > 0:
        print(f"Sample metadata entry: {metadata[0]}")
        print(f"Available envi_states: {[video['EnviState'] for video in metadata]}")
    
    # Create default emotions for video matching
    # Using neutral emotions since we don't have emotion data from manual entry
    default_emotions = {
        "joy": 0.5,
        "fear": 0.5,
        "anger": 0.5,
        "sadness": 0.5,
        "disgust": 0.5,
        "surprise": 0.5,
        "trust": 0.5
    }
    
    # Add all possible emotion keys that might be in the metadata
    for video in metadata:
        for key in video:
            if key not in ['Filename', 'EnviState'] and key not in default_emotions:
                try:
                    # Only add it if it looks like a numeric value
                    value = video[key]
                    if value != '.' and float(value):
                        default_emotions[key] = 0.5
                except (ValueError, TypeError):
                    pass
    
    print(f"Using emotion keys for matching: {list(default_emotions.keys())}")
    
    # Find matching video using the dictionary format
    matching_video = find_matching_video(request.envi_state, default_emotions)
    
    if not matching_video:
        print(f"No match found using emotions, trying direct envi_state match for: {request.envi_state}")
        # Fallback: select first video that has matching envi_state
        for video in metadata:
            if request.envi_state.lower() in video['EnviState'].lower() or video['EnviState'].lower() in request.envi_state.lower():
                matching_video = video['Filename']
                print(f"Using direct fallback match: {matching_video}")
                break
    
    if not matching_video and len(metadata) > 0:
        # Last resort fallback: just use the first video in metadata
        matching_video = metadata[0]['Filename']
        print(f"No match found, using first video as fallback: {matching_video}")
    
    if not matching_video:
        raise HTTPException(status_code=404, detail="No matching video found. Check if video_metadata.json exists and has entries.")
    
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
        "message": "Participant added to queue manually",
        "queue_position": len(request_queue),
        "video": matching_video,
        "channel": channel
    }

@app.post("/trigger_video")
async def trigger_video_endpoint(request: VideoRequest):
    """
    Endpoint to add a video request to the queue or first available slot
    """
    # Convert emotions to dictionary format if it's in list format
    emotions_dict = {}
    if isinstance(request.emotions, list):
        print("Converting emotions from list format to dictionary format")
        for emotion in request.emotions:
            emotions_dict[emotion.name] = emotion.score
    else:
        emotions_dict = request.emotions

    # Find matching video using the dictionary format
    matching_video = find_matching_video(request.envi_state, emotions_dict)
    
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

@app.post("/clear-queue")
async def clear_queue():
    """
    Clear the entire request queue
    """
    global request_queue
    
    print("Clearing request queue")
    request_queue.clear()  # Remove all items from the queue
    
    return {
        "status": "success",
        "message": "Request queue cleared"
    }

@app.post("/play-all")
async def play_all_videos(request: PlayAllRequest):
    """
    Play videos in sequence according to the choreography:
    1. Play intro video in layer 1 for 1m7s (67 seconds)
    2. Then play queued videos one by one in layer 2, each for 28 seconds
    3. After each video plays in layer 2, move it to the first available layer (3-8)
    4. After all videos have played, turn off layer 2 but keep others running
    """
    global current_play_task
    
    try:
        print(f"Received request to play {len(request.videos)} videos")
        videos = request.videos
        
        if len(videos) > 6:
            raise HTTPException(status_code=422, detail="Maximum 6 videos allowed")
        
        # Cancel any currently running task first
        if current_play_task and not current_play_task.done():
            print("Cancelling previous play sequence")
            current_play_task.cancel()
            try:
                await current_play_task
            except asyncio.CancelledError:
                print("Previous play sequence cancelled")
        
        # Start a background task to handle the sequence
        # This allows the API to return immediately while videos continue to play
        current_play_task = asyncio.create_task(play_video_sequence(videos))
        
        return {
            "status": "success",
            "message": "All videos triggered successfully in sequence"
        }
    except ValidationError as e:
        print(f"Validation error: {e}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        print(f"Error in play_all_videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def play_video_sequence(videos):
    """
    Handle the sequence of video playback in a background task
    
    Timing:
    1. Play intro video in layer 1 for 1m7s (120 seconds)
    2. Then play queued videos one by one in layer 2, each for 28 seconds
    3. After each video plays in layer 2, move it to the first available layer (3-8)
    4. After all videos have played, keep them running in layers 3-8 for 30 more seconds
    """
    try:
        # STEP 1: Play intro video in layer 1 (clip 2)
        print("Starting intro video in layer 1")
        # Trigger the intro video in layer 1, clip 2
        client.send_message("/composition/layers/1/clips/2/connect", 1)  
        
        # STEP 2: Wait for 1m7s (120 seconds) before starting first queued video
        print(f"Waiting 1m7s (120 seconds) for intro video...")
        
        # Check for cancellation during the 120-second wait
        for _ in range(120):
            # Check if task was cancelled
            if asyncio.current_task().cancelled():
                print("Play sequence task was cancelled - stopping")
                return
            await asyncio.sleep(1)
            
        print("Intro video complete, starting queued videos")
        
        # Track which layers (3-8) are already used
        used_layers = set()
        
        for i, video in enumerate(videos):
            # Check for cancellation
            if asyncio.current_task().cancelled():
                print("Play sequence task was cancelled - stopping")
                return
                
            print(f"\nProcessing video {i+1}:")
            print(f"Name: {video.name}")
            print(f"Challenge Point: {video.challenge_point}")
            print(f"Envi State: {video.envi_state}")
            print(f"Video: {video.video}")
            print(f"Channel: {video.channel}")
            
            # Trigger video in layer 2
            trigger_video(
                video.video,
                video.name,
                video.challenge_point,
                video.envi_state,
                2,  # Always use layer 2 for initial playback
                video.channel
            )
            
            # Wait 28 seconds
            print(f"Waiting 28 seconds for video {i+1} in layer 2...")
            
            # Check for cancellation during the 28-second wait
            for _ in range(28):
                if asyncio.current_task().cancelled():
                    print("Play sequence task was cancelled - stopping")
                    return
                await asyncio.sleep(1)
                
            print(f"Video {i+1} complete in layer 2")
            
            # Find the first available layer in range 3-8
            target_layer = None
            for layer in range(3, 9):
                if layer not in used_layers:
                    target_layer = layer
                    used_layers.add(layer)
                    break
                    
            # Move the video to the target layer if one was found
            if target_layer:
                print(f"Moving video {i+1} from layer 2 to layer {target_layer}")
                trigger_video(
                    video.video,
                    video.name,
                    video.challenge_point,
                    video.envi_state,
                    target_layer,
                    video.channel
                )
            else:
                print("No available layers left (3-8 are all used)")
        
        # After all videos, turn off layer 2 (square)
        print("All videos processed, turning off layer 2 (square)")
        toggle_layer(2, False)
        
        # Keep videos running for 30 more seconds in layers 3-8
        print("Keeping videos running for 30 more seconds in layers 3-8...")
        
        # Check for cancellation during the 30-second wait
        for _ in range(30):
            if asyncio.current_task().cancelled():
                print("Play sequence task was cancelled - stopping")
                return
            await asyncio.sleep(1)
                
        print("30 seconds passed, turning off all video layers")
        
        # Now turn off all the group layers (3-8)
        for layer in used_layers:
            print(f"Turning off layer {layer}")
            toggle_layer(layer, False)
            
        print("All videos complete. Experience finished.")
        
    except asyncio.CancelledError:
        print("Play sequence task was cancelled - exiting")
        raise
    except Exception as e:
        print(f"Error in play_video_sequence: {e}")
        # Try to turn off layer 2 in case of error
        try:
            toggle_layer(2, False)
        except:
            pass

@app.post("/needs_help", response_model=dict)
async def needs_help_endpoint(request: HelpRequest):
    """
    Set help status for a specific user. Can be used to start or stop help requests.
    Returns the current help status to be displayed in the web interface.
    
    - **user**: Name of the user or stage requiring assistance (e.g., 'Greeting', 'Name collection')
    - **needs_help**: Set to true to request help, false to cancel help request
    """
    global help_needed, help_user
    
    # Update help state based on the request
    help_needed = request.needs_help
    
    if help_needed:
        help_user = request.user
        message = f"{help_user} NEEDS HELP"
        print(f"[HELP REQUESTED]: {message}")
    else:
        previous_user = help_user
        help_user = ""
        message = f"Help request for {previous_user} resolved"
        print(f"[HELP RESOLVED]: {message}")
    
    return {
        "status": "success",
        "help_needed": help_needed,
        "help_user": help_user,
        "message": message
    }

@app.get("/help_status")
async def help_status():
    """
    Get the current help status
    """
    return {
        "help_needed": help_needed,
        "help_user": help_user,
        "message": f"{help_user} NEEDS HELP" if help_needed else "No help needed"
    }

@app.post("/stop-all")
async def stop_all_videos(request: BurnersToRemoveRequest = None):
    """
    Stop all videos, show splash screen in layer 1 (composition),
    and cancel any running play sequence.
    The frontend will handle clearing the slots.
    If burner data is provided, remove matching entries from the queue.
    """
    global current_play_task, request_queue
    
    try:
        print("Stopping all videos and cancelling play sequence")
        
        # Cancel the current play task if it exists and is running
        if current_play_task and not current_play_task.done():
            print("Cancelling running play sequence task")
            current_play_task.cancel()
            try:
                # Wait for the task to be cancelled (with a timeout)
                await asyncio.wait_for(asyncio.shield(current_play_task), 2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                print("Play sequence task cancelled or timeout occurred")
            current_play_task = None
        
        # Clear all layers 3-8 by triggering their empty column 1
        for layer in range(3, 9):
            try:
                # Clear this layer
                print(f"Clearing layer {layer} by triggering empty column 1")
                toggle_layer(layer, False)
            except Exception as e:
                print(f"Error clearing layer {layer}: {e}")
        
        # Clear layer 2 (square)
        print("Clearing layer 2 (square) by triggering empty column 1")
        toggle_layer(2, False)
        
        # For layer 1, trigger the splash screen which is in column 1
        print("Triggering splash screen in layer 1 (composition) at column 1")
        client.send_message("/composition/layers/1/clips/1/connect", 1)
        
        # Clear any text overlay in composition
        set_text_overlay("", 1)
        
        # If burner data to remove was provided, remove matching entries from the queue
        removed_count = 0
        if request and request.burners_to_remove:
            print(f"Removing {len(request.burners_to_remove)} burners from queue")
            
            # Create a new queue without the specified burners
            original_length = len(request_queue)
            new_queue = deque()
            
            for item in request_queue:
                # Keep the item unless it matches all criteria (name, challenge_point, envi_state)
                should_keep = True
                
                for burner in request.burners_to_remove:
                    # Check if all fields match
                    if (item["name"] == burner.name and 
                        item["challenge_point"] == burner.challenge_point and 
                        item["envi_state"] == burner.envi_state):
                        # This is a match, don't keep it
                        should_keep = False
                        break
                
                if should_keep:
                    new_queue.append(item)
            
            removed_count = original_length - len(new_queue)
            
            # Replace the queue with the filtered version
            request_queue = new_queue
            print(f"Removed {removed_count} burners from queue")
        
        return {
            "status": "success",
            "message": "All videos stopped and play sequence cancelled",
            "removed_burners": removed_count
        }
    except Exception as e:
        print(f"Error stopping videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clear-processed-burners")
async def clear_processed_burners(request: BurnersToRemoveRequest):
    """
    Remove specific burners from the request queue by matching all criteria.
    This is used when the Turning Point experience naturally completes, to remove 
    burners that have already gone through the experience.
    """
    global request_queue
    
    try:
        if not request.burners_to_remove:
            return {
                "status": "success",
                "message": "No burners to remove",
                "removed": 0
            }
        
        print(f"Removing {len(request.burners_to_remove)} processed burners from queue")
        for burner in request.burners_to_remove:
            print(f"  - Removing burner: {burner.name} ({burner.challenge_point} to {burner.envi_state})")
        
        # Debug: Print queue before removal
        print(f"Queue before removal (size: {len(request_queue)}):")
        for idx, item in enumerate(request_queue):
            print(f"  {idx}: {item['name']} ({item['challenge_point']} to {item['envi_state']})")
        
        # Create a new queue without the specified burners
        original_length = len(request_queue)
        new_queue = deque()
        
        for item in request_queue:
            # Keep the item unless it matches all criteria (name, challenge_point, envi_state)
            should_keep = True
            
            for burner in request.burners_to_remove:
                # Check if all fields match
                if (item["name"] == burner.name and 
                    item["challenge_point"] == burner.challenge_point and 
                    item["envi_state"] == burner.envi_state):
                    # This is a match, don't keep it
                    print(f"  Found match to remove: {item['name']} ({item['challenge_point']} to {item['envi_state']})")
                    should_keep = False
                    break
            
            if should_keep:
                new_queue.append(item)
        
        removed_count = original_length - len(new_queue)
        
        # Replace the queue with the filtered version
        request_queue = new_queue
        
        # Debug: Print queue after removal
        print(f"Queue after removal (size: {len(request_queue)}):")
        for idx, item in enumerate(request_queue):
            print(f"  {idx}: {item['name']} ({item['challenge_point']} to {item['envi_state']})")
        
        print(f"Removed {removed_count} burners from queue")
        
        return {
            "status": "success",
            "message": f"Removed {removed_count} burners from queue",
            "removed": removed_count
        }
    except Exception as e:
        print(f"Error removing burners: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/restart")
async def restart_turning_point():
    """
    Restart the Turning Point - clear videos and show splash screen
    but without deleting the names from the slots.
    The frontend will leave slot contents intact.
    """
    global current_play_task
    
    try:
        print("Restarting Turning Point (clearing layers without affecting slots)")
        
        # Cancel the current play task if it exists and is running
        if current_play_task and not current_play_task.done():
            print("Cancelling running play sequence task")
            current_play_task.cancel()
            try:
                # Wait for the task to be cancelled (with a timeout)
                await asyncio.wait_for(asyncio.shield(current_play_task), 2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                print("Play sequence task cancelled or timeout occurred")
            current_play_task = None
        
        # Clear all layers 3-8 by triggering their empty column 1
        for layer in range(3, 9):
            try:
                # Clear this layer
                print(f"Clearing layer {layer} by triggering empty column 1")
                toggle_layer(layer, False)
            except Exception as e:
                print(f"Error clearing layer {layer}: {e}")
        
        # Clear layer 2 (square)
        print("Clearing layer 2 (square) by triggering empty column 1")
        toggle_layer(2, False)
        
        # For layer 1, trigger the splash screen which is in column 1
        print("Triggering splash screen in layer 1 (composition) at column 1")
        client.send_message("/composition/layers/1/clips/1/connect", 1)
        
        # Clear any text overlay in composition
        set_text_overlay("", 1)
        
        return {
            "status": "success",
            "message": "Turning Point restarted (keeping slot contents intact)"
        }
    except Exception as e:
        print(f"Error restarting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/start-final-sequence")
async def start_final_sequence():
    """
    Start the final sequence of the Turning Point experience:
    1. Show the ending screen in layer 1
    2. Clear layer 2
    3. Keep videos in layers 3-8 running for the final 30 seconds
    """
    try:
        print("Starting final sequence")
        
        # For layer 1, show the ending screen which is in column 1
        print("Showing ending screen in layer 1 (composition) at column 1")
        client.send_message("/composition/layers/1/clips/1/connect", 1)
        
        # Clear layer 2 (square) as its video has finished
        print("Clearing layer 2 (square) by triggering empty column 1")
        toggle_layer(2, False)
        
        # Clear any text overlay in composition
        set_text_overlay("", 1)
        
        # Let layers 3-8 continue running - they'll be cleared by the frontend
        # after the 30-second countdown
        
        return {
            "status": "success",
            "message": "Final sequence started - videos in layers 3-8 will continue for 30 seconds"
        }
    except Exception as e:
        print(f"Error starting final sequence: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 