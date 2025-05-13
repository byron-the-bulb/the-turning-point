import time
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import welch
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes

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

def plot_brain_waves(band_powers_history):
    """
    Plot the power of each brain wave band over time.
    Updates the plot in real-time.
    """
    plt.clf()  # Clear the current figure
    for band, powers in band_powers_history.items():
        plt.plot(powers, label=band)
    plt.xlabel('Time (windows)')
    plt.ylabel('Power')
    plt.title('Brain Wave Powers Over Time')
    plt.legend()
    plt.pause(0.01)  # Brief pause to refresh the plot

def reject_artifacts(data, eeg_channels, threshold=200.0):
    """
    Check if any EEG channel exceeds the threshold (in μV).
    Prints max absolute values to debug the data range.
    Returns True if an artifact is detected.
    """
    artifact_detected = False
    for channel in eeg_channels:
        max_abs = np.max(np.abs(data[channel]))
        print(f"Channel {channel}: max abs = {max_abs:.2f} μV")
        if max_abs > threshold:
            artifact_detected = True
    if artifact_detected:
        print("Artifact detected in this window.")
        return True
    return False

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

def main():
    # Set up Brainflow parameters for Muse S
    params = BrainFlowInputParams()
    # Optionally, specify the MAC address if required: params.mac_address = "xx:xx:xx:xx:xx:xx"

    # Initialize the Muse S board
    board = BoardShim(BoardIds.MUSE_S_BOARD, params)

    try:
        # Prepare and start the EEG session
        board.prepare_session()
        print("Connected to Muse S. Sampling rate: " + str(SAMPLING_RATE))
        eeg_channels = BoardShim.get_eeg_channels(BoardIds.MUSE_S_BOARD)

        print("EEG channels: " + str(eeg_channels))
        board.start_stream()
        print("Streaming EEG data... Press Ctrl-C to stop.")

        # Initialize a history dictionary to store band powers over time
        band_powers_history = {band: [] for band in BANDS}

        # Set up real-time plotting
        plt.ion()  # Turn on interactive mode
        plt.figure()

        # Main loop: Stream and process data until interrupted
        while True:
            # Check how many samples are available in the buffer
            num_samples_available = board.get_board_data_count()
            if num_samples_available < WINDOW_SIZE:
                time.sleep(0.1)  # Wait briefly if not enough data
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

            # Update the plot
            plot_brain_waves(band_powers_history)

            # Small delay to prevent high CPU usage
            time.sleep(0.01)


    except KeyboardInterrupt:
        print("\nStopping stream...")
        distilled_summary = distill_eeg_data(band_powers_history)
        print("Distilled EEG Summary for LLM:")
        print(distilled_summary)
    finally:
        # Clean up: Stop the stream and release the session
        board.stop_stream()
        board.release_session()
        print("Disconnected from Muse S")

if __name__ == "__main__":
    main()