import time
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import threading
import uvicorn
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes
from scipy.signal import welch

app = FastAPI(title="Muse EEG API", description="REST API for Muse EEG headband")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define brain wave frequency bands (in Hz)
BANDS = {
    'Theta': (4, 8),    # 4–8 Hz
    'Alpha': (8, 12),   # 8–12 Hz
    'Beta': (12, 30),   # 12–30 Hz
    'Gamma': (30, 100)  # 30–100 Hz
}

# Sampling rate for Muse S (Hz)
SAMPLING_RATE = BoardShim.get_sampling_rate(BoardIds.MUSE_S_BOARD)

# Window size for processing (2 seconds of data)
WINDOW_LENGTH_SECONDS = 2
WINDOW_SIZE = WINDOW_LENGTH_SECONDS * SAMPLING_RATE

# Global variables for recording state and data storage
board = None
eeg_buffer = {band: [] for band in BANDS}
recording = False
recording_start_time = None  # Track when recording started
lock = threading.Lock()

def initialize_board():
    """Initialize connection to the Muse headband"""
    global board
    if board is not None:
        return

    # Set up Brainflow parameters for Muse S
    params = BrainFlowInputParams()
    # Optionally, specify the MAC address if required: params.mac_address = "xx:xx:xx:xx:xx:xx"

    try:
        # Initialize the Muse S board
        board = BoardShim(BoardIds.MUSE_S_BOARD, params)
        board.prepare_session()
        print("Connected to Muse S. Sampling rate: " + str(SAMPLING_RATE))
    except Exception as e:
        board = None
        raise Exception(f"Failed to connect to Muse headband: {str(e)}")

def preprocess_data(data, eeg_channels):
    """
    Clean the raw EEG data by applying filters to remove noise.
    - Bandpass filter: Keep frequencies between 0.5–50 Hz
    - Notch filter: Remove 50 Hz power line noise (adjust to 60 Hz if needed)
    """
    for channel in eeg_channels:
        # Apply bandpass filter to remove low-frequency drift and high-frequency noise
        DataFilter.perform_bandpass(
            data[channel], SAMPLING_RATE, 0.5, 50.0, 4, FilterTypes.BUTTERWORTH.value, 0
        )
        # Apply notch filter to remove power line interference
        DataFilter.perform_bandstop(
            data[channel], SAMPLING_RATE, 48.0, 52.0, 4, FilterTypes.BUTTERWORTH.value, 0
        )
    return data

def reject_artifacts(data, eeg_channels, threshold=200.0):
    """
    Check if any EEG channel exceeds the threshold (in μV).
    Returns True if an artifact is detected.
    """
    artifact_detected = False
    for channel in eeg_channels:
        max_abs = np.max(np.abs(data[channel]))
        if max_abs > threshold:
            artifact_detected = True
    if artifact_detected:
        print("Artifact detected in this window.")
        return True
    return False

def compute_band_powers(data, eeg_channels):
    """
    Calculate the power in each brain wave band using Welch's method.
    Returns a dictionary with average power for each band across all channels.
    """
    band_powers = {band: [] for band in BANDS}
    for channel in eeg_channels:
        # Compute power spectral density (PSD) using Welch's method
        freqs, psd = welch(data[channel], fs=SAMPLING_RATE, nperseg=WINDOW_SIZE)
        for band, (low, high) in BANDS.items():
            # Find indices for the frequency band
            idx = np.where((freqs >= low) & (freqs < high))[0]
            # Sum the power in this band
            power = np.sum(psd[idx])
            band_powers[band].append(power)
    # Average the power across all channels
    avg_band_powers = {band: np.mean(powers) for band, powers in band_powers.items()}
    return avg_band_powers

def distill_eeg_data(band_powers_history, session_duration_minutes=None, segment_length_minutes=0.5):
    """
    Summarize EEG brain wave data into concise segments for LLM input.
    
    Args:
        band_powers_history (dict): Dictionary with band powers over time (e.g., {"Alpha": [10.5, ...], ...})
        session_duration_minutes (float): Total session duration in minutes (if known)
        segment_length_minutes (float): Length of each segment in minutes
    
    Returns:
        str: A distilled text summary for the LLM
    """
    # Calculate windows per minute
    windows_per_minute = 60 / WINDOW_LENGTH_SECONDS
    total_windows = len(band_powers_history["Alpha"]) / WINDOW_SIZE

    print(f"Total windows: {total_windows}")
    print(f"Windows per minute: {windows_per_minute}")
    
    # Estimate session duration if not provided
    if session_duration_minutes is None:
        session_duration_minutes = total_windows / windows_per_minute

    print(f"Session duration: {session_duration_minutes} minutes")
    
    segment_windows = int(segment_length_minutes * windows_per_minute)
    
    # Compute global thresholds for notable peaks (75th percentile)
    thresholds = {band: np.percentile(powers, 75) for band, powers in band_powers_history.items()}
    
    summaries = []
    for start in range(0, total_windows, segment_windows):
        end = min(start + segment_windows, total_windows)
        segment_data = {band: band_powers_history[band][start:end] for band in band_powers_history}
        
        # Compute statistics for the segment
        segment_summary = {}
        for band in segment_data:
            powers = np.array(segment_data[band])
            segment_summary[band] = {
                "mean": np.mean(powers),
                "std": np.std(powers),
                "peak": np.max(powers)
            }
        
        # Identify notable peaks (above 75th percentile)
        notes = []
        for band in segment_summary:
            if segment_summary[band]["peak"] > thresholds[band]:
                notes.append(f"{band} peak: {segment_summary[band]['peak']:.1f}")
        
        # Format the segment summary
        start_minute = start / windows_per_minute
        end_minute = end / windows_per_minute
        summary_line = (
            f"Min {start_minute:.1f}–{end_minute:.1f}: "
            f"A {segment_summary['Alpha']['mean']:.1f}±{segment_summary['Alpha']['std']:.1f}, "
            f"B {segment_summary['Beta']['mean']:.1f}±{segment_summary['Beta']['std']:.1f}, "
            f"T {segment_summary['Theta']['mean']:.1f}±{segment_summary['Theta']['std']:.1f}, "
            f"G {segment_summary['Gamma']['mean']:.1f}±{segment_summary['Gamma']['std']:.1f}"
        )
        if notes:
            summary_line += f" ({', '.join(notes)})"
        summaries.append(summary_line)
    
    return "\n".join(summaries)

def record_eeg_data():
    """Background thread function to record EEG data"""
    global board, eeg_buffer, recording
    
    eeg_channels = BoardShim.get_eeg_channels(BoardIds.MUSE_S_BOARD)
    print(f"EEG channels used: {eeg_channels}")
    
    # Initialize a history dictionary to store band powers over time
    band_powers_history = {band: [] for band in BANDS}
    
    while recording:
        try:
            # Check how many samples are available in the buffer
            num_samples_available = board.get_board_data_count()
            if num_samples_available < WINDOW_SIZE:
                time.sleep(0.01)  # Wait briefly if not enough data
                continue
            
            # Retrieve and remove exactly WINDOW_SIZE samples
            data = board.get_board_data(WINDOW_SIZE)
            
            # Clean the data
            preprocessed_data = preprocess_data(data, eeg_channels)
            
            # Compute power in each brain wave band
            band_powers = compute_band_powers(preprocessed_data, eeg_channels)
            
            # Store the results in history
            for band in BANDS:
                band_powers_history[band].append(band_powers[band])
            
            # Add to buffer
            with lock:
                eeg_buffer = band_powers_history  # Store the band powers history
            
            time.sleep(0.01)  # Small delay to prevent high CPU usage
            
        except Exception as e:
            print(f"Error in record_eeg_data: {str(e)}")
            recording = False
            break

@app.get("/")
def read_root():
    """Root endpoint"""
    return {"message": "Muse EEG API is running"}

@app.get("/status")
def check_connection():
    """Check if Muse headband is connected"""
    global board
    
    if board is None:
        try:
            initialize_board()
            return {"connected": True}
        except Exception as e:
            return {"connected": False, "error": str(e)}
    
    return {"connected": True}

@app.post("/start")
def start_recording():
    """Clear buffer and start recording new EEG data"""
    global board, eeg_buffer, recording, recording_start_time
    
    if board is None:
        raise HTTPException(status_code=400, detail="Muse headband not connected")
    
    if recording:
        raise HTTPException(status_code=400, detail="Already recording")
    
    # Clear buffer
    with lock:
        eeg_buffer = {band: [] for band in BANDS}
    
    # Start recording and track start time
    recording = True
    recording_start_time = time.time()
    
    # Start EEG stream if it's not already running
    try:
        if not board.is_prepared():
            board.prepare_session()
        
        # Check if already streaming
        try:
            board.start_stream()
        except Exception as e:
            if "already streaming" not in str(e).lower():
                raise  # Re-raise if it's a different error
        
        # Start background thread for data collection
        record_thread = threading.Thread(target=record_eeg_data)
        record_thread.daemon = True  # Thread will exit when main program exits
        record_thread.start()
    except Exception as e:
        recording = False
        recording_start_time = None
        raise HTTPException(status_code=500, detail=f"Error starting recording: {str(e)}")
    
    return {"status": "success", "message": "Recording started"}

@app.post("/stop")
def stop_recording():
    """Stop recording EEG data and return distilled summary"""
    global board, eeg_buffer, recording, recording_start_time
    
    if board is None:
        raise HTTPException(status_code=400, detail="Muse headband not connected")
    
    if not recording:
        raise HTTPException(status_code=400, detail="Not currently recording")
    
    # Stop recording
    recording = False
    try:
        board.stop_stream()
    except Exception as e:
        print(f"Error stopping stream: {str(e)}")
    
    # Get the buffer content
    with lock:
        band_powers_history = eeg_buffer
        # Verify we have data
        if not band_powers_history or not band_powers_history.get('Alpha'):
            return {
                "status": "error",
                "message": "No EEG data was recorded",
                "distilled_summary": ""
            }
    
    # Calculate the actual recording duration in minutes
    recording_duration_minutes = None
    if recording_start_time is not None:
        recording_duration_seconds = time.time() - recording_start_time
        recording_duration_minutes = recording_duration_seconds / 60.0
        print(f"Recording duration: {recording_duration_seconds:.2f} seconds ({recording_duration_minutes:.2f} minutes)")
    
    # Process the band powers to create a distilled summary
    try:
        # Pass the actual recording duration to the distill function
        distilled_summary = distill_eeg_data(band_powers_history, 
                                          session_duration_minutes=recording_duration_minutes)
        
        # Reset the buffer and recording start time
        with lock:
            eeg_buffer = {band: [] for band in BANDS}
            recording_start_time = None
    except Exception as e:
        print(f"Error processing EEG data: {str(e)}")
        recording_start_time = None
        return {
            "status": "error",
            "message": f"Error processing EEG data: {str(e)}",
            "distilled_summary": ""
        }
    
    return {
        "status": "success", 
        "message": "Recording stopped and data processed", 
        "samples": len(band_powers_history.get('Alpha', [])),
        "distilled_summary": distilled_summary
    }

@app.on_event("shutdown")
def shutdown_event():
    """Clean up resources when shutting down"""
    global board, recording
    
    recording = False
    
    if board is not None:
        try:
            if board.is_prepared():
                board.stop_stream()
                board.release_session()
            print("Disconnected from Muse S")
        except Exception as e:
            print(f"Error during shutdown: {str(e)}")

if __name__ == "__main__":
    try:
        # Try to initialize the board at startup
        initialize_board()
    except Exception as e:
        print(f"Warning: Could not connect to Muse headband at startup: {str(e)}")
        print("You can still connect later via the API endpoints")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
