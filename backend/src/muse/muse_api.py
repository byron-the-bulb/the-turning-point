import time
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import threading
import uvicorn
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes, NoiseTypes
from brainflow.ml_model import MLModel, BrainFlowMetrics, BrainFlowClassifiers, BrainFlowModelParams
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
    'Delta': (0.5, 4),   # 0.5–4 Hz
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
mindfulness_scores = []  # List of (timestamp, score) tuples
mindfulness_model = None  # Global mindfulness model
processed_data_history = []  # Store data for mindfulness calculations
lock = threading.Lock()

def initialize_board():
    """Initialize connection to the Muse headband and mindfulness model"""
    global board, mindfulness_model
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
        
        # Initialize mindfulness model
        mindfulness_params = BrainFlowModelParams(BrainFlowMetrics.MINDFULNESS.value,
                                           BrainFlowClassifiers.DEFAULT_CLASSIFIER.value)
        mindfulness_model = MLModel(mindfulness_params)
        mindfulness_model.prepare()
        print("Mindfulness model prepared.")
    except Exception as e:
        board = None
        mindfulness_model = None
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
            data[channel], SAMPLING_RATE, 2.0, 50.0, 4, FilterTypes.BESSEL_ZERO_PHASE.value, 0
        )
        # Apply notch filter to remove power line interference
        DataFilter.perform_bandstop(
            data[channel], SAMPLING_RATE, 48.0, 52.0, 3, FilterTypes.BUTTERWORTH_ZERO_PHASE.value, 0
        )
        DataFilter.remove_environmental_noise(data[channel], SAMPLING_RATE, NoiseTypes.FIFTY.value)
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

def compute_band_powers_per_channel(data, eeg_channels):
    """
    Calculate the power in each brain wave band using Welch's method for each channel separately.
    Returns a list of dictionaries, where each dictionary contains band powers for one channel.
    """
    band_powers_per_channel = []
    for channel in eeg_channels:
        # Compute power spectral density (PSD) using Welch's method
        freqs, psd = welch(data[channel], fs=SAMPLING_RATE, nperseg=WINDOW_SIZE)
        channel_powers = {}
        for band, (low, high) in BANDS.items():
            # Find indices for the frequency band
            idx = np.where((freqs >= low) & (freqs < high))[0]
            # Sum the power in this band
            power = np.sum(psd[idx])
            channel_powers[band] = power
        band_powers_per_channel.append(channel_powers)
    return band_powers_per_channel

def compute_band_powers_per_channel_fast(data, eeg_channels, sampling_rate):
    """
    Efficiently calculate power in each brain wave band for each channel.
    Uses BrainFlow's optimized methods for better performance.
    """
    bands_all_channels = []
    for channel in eeg_channels:
        # Compute PSD for the channel
        psd = DataFilter.get_psd_welch(data[channel], WINDOW_SIZE, WINDOW_SIZE // 2, sampling_rate, 0)
        # Extract band powers
        bands_all_channels.append({band: DataFilter.get_band_power(psd, BANDS[band][0], BANDS[band][1]) for band in BANDS})

    return bands_all_channels

def distill_eeg_data(band_powers_history, mindfulness_scores=None, session_duration_minutes=None, segment_length_minutes=0.5):
    """
    Summarize EEG brain wave data into concise segments for LLM input.
    
    Args:
        band_powers_history (dict): Dictionary with band powers over time (e.g., {"Alpha": [10.5, ...], ...})
        mindfulness_scores (list): List of tuples (timestamp_in_seconds, score) with mindfulness scores
        session_duration_minutes (float): Total session duration in minutes (if known)
        segment_length_minutes (float): Length of each segment in minutes
    
    Returns:
        str: A distilled text summary for the LLM
    """
    # Get the total number of windows in our data
    total_windows = len(band_powers_history["Alpha"])
    
    # Calculate windows per minute based on sampling parameters
    # Each window is WINDOW_LENGTH_SECONDS long
    windows_per_minute = 60.0 / WINDOW_LENGTH_SECONDS
    
    print(f"Total windows: {total_windows}")
    print(f"Windows per minute: {windows_per_minute}")
    
    # Calculate actual session duration from the number of windows collected
    actual_duration_minutes = total_windows / windows_per_minute
    
    # Use provided duration if specified, otherwise use calculated duration
    if session_duration_minutes is None:
        session_duration_minutes = actual_duration_minutes
    
    print(f"Actual session duration: {actual_duration_minutes:.2f} minutes ({actual_duration_minutes*60:.1f} seconds)")
    
    # Calculate number of windows per segment
    segment_windows = int(segment_length_minutes * windows_per_minute)
    
    # Compute global thresholds for notable peaks (75th percentile)
    thresholds = {band: np.percentile(powers, 75) for band, powers in band_powers_history.items()}
    
    # Process mindfulness scores if available
    mindfulness_by_segment = {}
    if mindfulness_scores:
        for timestamp, score in mindfulness_scores:
            # Convert timestamp to segment index
            segment_idx = int(timestamp / (segment_length_minutes * 60))
            mindfulness_by_segment[segment_idx] = score
    
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
        
        # Calculate the actual minutes based on the proportion of the session
        # This ensures timestamps accurately reflect the real recording duration
        start_proportion = start / total_windows
        end_proportion = end / total_windows
        start_minute = start_proportion * actual_duration_minutes
        end_minute = end_proportion * actual_duration_minutes
        
        # Get segment index for mindfulness score lookup
        segment_idx = start // segment_windows
        
        # Build the summary line with brain wave data
        summary_line = (
            f"Min {start_minute:.1f}–{end_minute:.1f}: "
            f"D {segment_summary['Delta']['mean']:.1f}±{segment_summary['Delta']['std']:.1f}, "
            f"A {segment_summary['Alpha']['mean']:.1f}±{segment_summary['Alpha']['std']:.1f}, "
            f"B {segment_summary['Beta']['mean']:.1f}±{segment_summary['Beta']['std']:.1f}, "
            f"T {segment_summary['Theta']['mean']:.1f}±{segment_summary['Theta']['std']:.1f}, "
            f"G {segment_summary['Gamma']['mean']:.1f}±{segment_summary['Gamma']['std']:.1f}"
        )
        
        # Add mindfulness score if available for this segment
        if mindfulness_by_segment and segment_idx in mindfulness_by_segment:
            # Ensure the value is a float before formatting
            mind_value = mindfulness_by_segment[segment_idx]
            summary_line += f", Mindfulness: {mind_value:.2f}"
        if notes:
            summary_line += f" ({', '.join(notes)})"
        summaries.append(summary_line)
    
    return "\n".join(summaries)

def record_eeg_data():
    """Background thread function to record EEG data"""
    global board, eeg_buffer, recording, mindfulness_scores, mindfulness_model, processed_data_history
    
    eeg_channels = BoardShim.get_eeg_channels(BoardIds.MUSE_S_BOARD)
    print(f"EEG channels used: {eeg_channels}")
    
    # Initialize a history dictionary to store band powers over time
    band_powers_history = {band: [] for band in BANDS}
    processed_data_history = []
    
    # Reset mindfulness scores
    mindfulness_scores = []
    
    # Counter for loop iterations
    loop_count = 0
    
    while recording:
        try:
            # Start performance timer for this loop iteration
            loop_start_time = time.time()
            
            # Check how many samples are available in the buffer
            num_samples_available = board.get_board_data_count()
            if num_samples_available < WINDOW_SIZE:
                time.sleep(0.01)  # Wait briefly if not enough data
                continue
            
            # Reset timer after continue since we're starting a new iteration with data
            loop_start_time = time.time()
            
            # Retrieve and remove exactly WINDOW_SIZE samples
            data = board.get_board_data(WINDOW_SIZE)
            
            # Clean the data
            preprocessed_data = preprocess_data(data, eeg_channels)
            
            # Compute band powers for each channel individually using the faster method
            band_powers_per_channel = compute_band_powers_per_channel_fast(preprocessed_data, eeg_channels, SAMPLING_RATE)
            
            # Compute average band powers across channels
            avg_band_powers = {}
            std_band_powers = {}
            for band in BANDS:
                # Extract band powers for this band from all channels
                band_powers = [ch_powers[band] for ch_powers in band_powers_per_channel]
                avg_band_powers[band] = np.mean(band_powers)
                std_band_powers[band] = np.std(band_powers)
            
            # Store the results in history
            for band in BANDS:
                band_powers_history[band].append(avg_band_powers[band])
            
            # Add to buffer with thread safety
            with lock:
                eeg_buffer = band_powers_history
            
            # Store processed data for mindfulness calculations
            processed_data_history.append(preprocessed_data)
            
            # Every 4 windows, compute mindfulness score
            if len(processed_data_history) % 4 == 0 and mindfulness_model is not None:
                try:
                    # Concatenate the last 4 windows of data
                    concatenated_data = np.concatenate(processed_data_history[-4:], axis=1)
                    
                    # Get average band powers in BrainFlow format
                    avg_band_powers_bf = DataFilter.get_avg_band_powers(
                        concatenated_data, eeg_channels, SAMPLING_RATE, True
                    )
                    
                    # Construct the feature vector
                    feature_vector = avg_band_powers_bf[0]
                    
                    # Predict mindfulness
                    mindfulness_score = mindfulness_model.predict(feature_vector)
                    
                    # Calculate timestamp in seconds from the beginning of the session
                    current_timestamp = (loop_count * WINDOW_LENGTH_SECONDS)
                    
                    # Convert to float and store with timestamp
                    mindfulness_value = float(mindfulness_score[0]) if hasattr(mindfulness_score, '__iter__') else float(mindfulness_score)
                    with lock:
                        mindfulness_scores.append((current_timestamp, mindfulness_value))
                    
                    print(f"Mindfulness score: {mindfulness_value:.2f} at {current_timestamp:.1f} seconds")
                except Exception as e:
                    print(f"Error predicting mindfulness: {str(e)}")
            
            # Calculate execution time for this loop iteration
            loop_end_time = time.time()
            loop_duration = loop_end_time - loop_start_time
            loop_count += 1
            print(f"Loop {loop_count} execution time: {loop_duration:.6f} seconds (processing {WINDOW_SIZE} samples)")
            
            time.sleep(0.01)  # Small delay to prevent high CPU usage
            
        except Exception as e:
            print(f"Error in record_eeg_data: {str(e)}")
            recording = False
            break

@app.get("/")
def read_root():
    """Root endpoint"""
    return {"message": "Muse EEG API is running"}

@app.get("/data")
def get_current_data(distill_window: Optional[float] = 5.0):
    """Get the current distilled EEG data without stopping the recording
    
    Args:
        distill_window: Number of seconds in the past to distill data for (default: 5.0)
    """
    global board, eeg_buffer, recording, recording_start_time, mindfulness_scores
    
    if board is None:
        raise HTTPException(status_code=400, detail="Muse headband not connected")
    
    if not recording:
        raise HTTPException(status_code=400, detail="Not currently recording")
    
    # Get the current buffer content with thread safety
    with lock:
        band_powers_history = eeg_buffer.copy()
        local_mindfulness_scores = mindfulness_scores.copy() if mindfulness_scores else []
        # Verify we have data
        if not band_powers_history or not band_powers_history.get('Alpha'):
            return {
                "status": "error",
                "message": "No EEG data recorded yet",
                "data": {}
            }
    
    # Calculate the current recording duration in minutes
    recording_duration_minutes = None
    if recording_start_time is not None:
        recording_duration_seconds = time.time() - recording_start_time
        recording_duration_minutes = recording_duration_seconds / 60.0
    
    # Process the band powers to create a distilled summary
    try:
        # Get the total number of windows in our data
        total_windows = len(band_powers_history["Alpha"])
        windows_per_minute = 60.0 / WINDOW_LENGTH_SECONDS
        windows_per_second = windows_per_minute / 60.0
        
        # Calculate how many windows we need based on distill_window (in seconds)
        windows_needed = int(distill_window * windows_per_second)
        
        # Make sure we don't try to get more windows than we have
        windows_needed = min(windows_needed, total_windows)
        
        # Extract only the most recent windows of data
        start_idx = total_windows - windows_needed
        recent_data = {}
        for band in band_powers_history:
            recent_data[band] = band_powers_history[band][start_idx:]
        
        # Compute statistics for the recent data
        segment_summary = {}
        for band in recent_data:
            powers = np.array(recent_data[band])
            segment_summary[band] = {
                "mean": float(np.mean(powers)),
                "std": float(np.std(powers)),
                "peak": float(np.max(powers))
            }
        
        # Compute thresholds for notable peaks (75th percentile) using the full history
        # for more stable thresholds
        thresholds = {band: np.percentile(band_powers_history[band], 75) for band in band_powers_history}
        
        # Identify notable peaks
        notes = []
        for band in segment_summary:
            if segment_summary[band]["peak"] > thresholds[band]:
                notes.append(f"{band} peak: {segment_summary[band]['peak']:.1f}")
        
        # Calculate the time range in seconds relative to the recording start
        start_seconds = (start_idx / windows_per_second)
        end_seconds = recording_duration_seconds
        
        # Find relevant mindfulness scores within this time window
        mindfulness_value = None
        if local_mindfulness_scores:
            # Filter to only include scores within our time window
            recent_scores = [(timestamp, score) for timestamp, score in local_mindfulness_scores 
                           if timestamp >= start_seconds]
            
            if recent_scores:
                # Use the average of recent scores within the window
                mindfulness_value = float(np.mean([score for _, score in recent_scores]))
            else:
                # No scores in the window, find the closest one
                # Convert time window start to seconds
                distances = [(abs(timestamp - start_seconds), score) for timestamp, score in local_mindfulness_scores]
                # Sort by distance (closest first)
                distances.sort(key=lambda x: x[0])
                # Use the closest score
                if distances:
                    mindfulness_value = float(distances[0][1])
        
        # Build segment data
        segment = {
            "time_range": {
                "start_seconds": float(start_seconds),
                "end_seconds": float(end_seconds),
                "start_minute": float(start_seconds / 60.0),
                "end_minute": float(end_seconds / 60.0)
            },
            "brain_waves": segment_summary,
            "notable_peaks": notes,
            "mindfulness": mindfulness_value
        }
        
        return {
            "status": "success",
            "message": "Current EEG data processed",
            "recording_duration": {
                "seconds": float(recording_duration_seconds),
                "minutes": float(recording_duration_minutes)
            },
            "window_seconds": float(distill_window),
            "actual_window_seconds": float(windows_needed / windows_per_second),
            "samples": windows_needed,
            "mindfulness_samples": len([s for t, s in local_mindfulness_scores if t >= start_seconds]),
            "segment": segment
        }
    except Exception as e:
        print(f"Error processing current EEG data: {str(e)}")
        return {
            "status": "error",
            "message": f"Error processing EEG data: {str(e)}",
            "data": {}
        }

@app.get("/status")
def check_connection():
    """Check if Muse headband is connected and recording status"""
    global board, recording
    
    if board is None:
        try:
            initialize_board()
            return {"connected": True, "recording": recording}
        except Exception as e:
            return {"connected": False, "recording": False, "error": str(e)}
    
    return {"connected": True, "recording": recording}

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
    global board, eeg_buffer, recording, recording_start_time, mindfulness_scores, mindfulness_model
    
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
    
    # Get the buffer content with thread safety
    with lock:
        band_powers_history = eeg_buffer
        local_mindfulness_scores = mindfulness_scores.copy() if mindfulness_scores else []
        # Verify we have data
        if not band_powers_history or not band_powers_history.get('Alpha'):
            return {
                "status": "error",
                "message": "No EEG data was recorded",
                "distilled_summary": "",
                "mindfulness_scores": []
            }
    
    # Calculate the actual recording duration in minutes
    recording_duration_minutes = None
    if recording_start_time is not None:
        recording_duration_seconds = time.time() - recording_start_time
        recording_duration_minutes = recording_duration_seconds / 60.0
        print(f"Recording duration: {recording_duration_seconds:.2f} seconds ({recording_duration_minutes:.2f} minutes)")
    
    # Process the band powers to create a distilled summary
    try:
        # Pass the actual recording duration and mindfulness scores to the distill function
        distilled_summary = distill_eeg_data(band_powers_history, 
                                         mindfulness_scores=local_mindfulness_scores,
                                         session_duration_minutes=recording_duration_minutes)
        
        # Reset the buffer, mindfulness scores and recording start time
        with lock:
            eeg_buffer = {band: [] for band in BANDS}
            mindfulness_scores = []
            recording_start_time = None
    except Exception as e:
        print(f"Error processing EEG data: {str(e)}")
        recording_start_time = None
        return {
            "status": "error",
            "message": f"Error processing EEG data: {str(e)}",
            "distilled_summary": "",
            "mindfulness_scores": []
        }
    
    return {
        "status": "success", 
        "message": "Recording stopped and data processed", 
        "samples": len(band_powers_history.get('Alpha', [])),
        "mindfulness_samples": len(local_mindfulness_scores),
        "distilled_summary": distilled_summary,
        "mindfulness_scores": local_mindfulness_scores
    }

@app.on_event("shutdown")
def shutdown_event():
    """Clean up resources when shutting down"""
    global board, recording, mindfulness_model
    
    recording = False
    
    # Release the mindfulness model
    if mindfulness_model is not None:
        try:
            mindfulness_model.release()
            print("Released mindfulness model resources")
        except Exception as e:
            print(f"Error releasing mindfulness model: {str(e)}")
    
    # Release the board
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
