import time
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import welch
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, FilterTypes, NoiseTypes
from brainflow.ml_model import MLModel, BrainFlowMetrics, BrainFlowClassifiers, BrainFlowModelParams

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
    bands_all_channels = []
    for channel in eeg_channels:
        # Compute PSD for the channel
        psd = DataFilter.get_psd_welch(data[channel], WINDOW_SIZE, WINDOW_SIZE // 2, sampling_rate, 0)
        # Extract band powers
        bands_all_channels.append({band: DataFilter.get_band_power(psd, BANDS[band][0], BANDS[band][1]) for band in BANDS})

    return bands_all_channels

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

def distill_eeg_data(band_powers_history, mindfulness_scores=None, session_duration_minutes=None, segment_length_minutes=0.5):
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

def main():
    print("BrainFlow version: " + BoardShim.get_version())
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

        # Initialize mindfulness model
        mindfulness_params = BrainFlowModelParams(BrainFlowMetrics.MINDFULNESS.value,
                                              BrainFlowClassifiers.DEFAULT_CLASSIFIER.value)
        mindfulness = MLModel(mindfulness_params)
        mindfulness.prepare()
        print("Mindfulness model prepared.")
        # Initialize a history dictionary to store band powers over time
        band_powers_history = {band: [] for band in BANDS}
        processed_data_history = []
        
        # Initialize list to store mindfulness scores with timestamps
        # Each entry will be a tuple of (timestamp_in_seconds, score)
        mindfulness_scores = []

        # Set up real-time plotting
        plt.ion()  # Turn on interactive mode
        plt.figure()

        # Main loop: Stream and process data until interrupted
        loop_count = 0
        while True:
            # Start performance timer for this loop iteration
            loop_start_time = time.time()
            
            # Check how many samples are available in the buffer
            num_samples_available = board.get_board_data_count()
            if num_samples_available < WINDOW_SIZE:
                time.sleep(0.1)  # Wait briefly if not enough data
                continue
                
            # Reset timer after continue since we're starting a new iteration with data
            loop_start_time = time.time()

            # Retrieve and remove exactly WINDOW_SIZE samples
            data = board.get_board_data(WINDOW_SIZE)

            # Clean the data
            preprocessed_data = preprocess_data(data, eeg_channels)

            # Compute band powers for each channel individually
            band_powers_per_channel = compute_band_powers_per_channel_fast(preprocessed_data, eeg_channels, SAMPLING_RATE)
            #print("Band powers per channel:", band_powers_per_channel)
            # Compute average and standard deviation of band powers across channels
            avg_band_powers = {}
            std_band_powers = {}
            for band in BANDS:
                # Extract band powers for this band from all channels
                band_powers = [ch_powers[band] for ch_powers in band_powers_per_channel]
                avg_band_powers[band] = np.mean(band_powers)
                std_band_powers[band] = np.std(band_powers)
        
            # Log the averages for debugging (optional)
            #print("Average band powers:", avg_band_powers)
            #print("Standard deviation of band powers:", std_band_powers)
        
            # Aggregate band powers for history (averaging across channels for plotting)
            for band in BANDS:
                band_powers_history[band].append(avg_band_powers[band])

            # Update the plot
            plot_brain_waves(band_powers_history)
            
            processed_data_history.append(preprocessed_data)

            # Every 4 windows we will compute the mindfulness score
            if len(processed_data_history) % 4 == 0:
                # Convert list of arrays to a single concatenated numpy array
                # Assuming each array in processed_data_history has the same shape
                concatenated_data = np.concatenate(processed_data_history[-4:], axis=1)
                avg_band_powers_bf = DataFilter.get_avg_band_powers(
                    concatenated_data, eeg_channels, SAMPLING_RATE, True
                )   
                # Construct the feature vector: [avg_delta, avg_theta, ..., avg_gamma, std_delta, std_theta, ..., std_gamma]
                feature_vector = avg_band_powers_bf[0]
                
                # Apply log transformation to stabilize values (optional but recommended)
                #feature_vector = np.log1p(feature_vector)
                #print("Feature vector:", feature_vector)            
            
                # Predict mindfulness
                try:
                    mindfulness_score = mindfulness.predict(feature_vector)
                    
                    # Calculate timestamp in seconds from the beginning of the session
                    current_timestamp = (loop_count * WINDOW_LENGTH_SECONDS)
                    
                    # Store mindfulness score with its timestamp
                    # BrainFlow returns a numpy array, so we need to convert it to a float
                    mindfulness_value = float(mindfulness_score[0]) if hasattr(mindfulness_score, '__iter__') else float(mindfulness_score)
                    mindfulness_scores.append((current_timestamp, mindfulness_value))
                    
                    print(f"Mindfulness score: {mindfulness_value:.2f} at {current_timestamp:.1f} seconds")
                except Exception as e:
                    print(f"Error predicting mindfulness: {str(e)}")            

            # Calculate and print the execution time for this loop iteration
            loop_end_time = time.time()
            loop_duration = loop_end_time - loop_start_time
            loop_count += 1
            print(f"Loop {loop_count} execution time: {loop_duration:.6f} seconds (processing {WINDOW_SIZE} samples)")
            
            # Small delay to prevent high CPU usage
            time.sleep(0.01)


    except KeyboardInterrupt:
        print("\nStopping stream...")
        distilled_summary = distill_eeg_data(band_powers_history, mindfulness_scores)
        print("Distilled EEG Summary for LLM:")
        print(distilled_summary)
    finally:
        # Clean up: Stop the stream and release the session
        mindfulness.release()
        board.stop_stream()
        board.release_session()
        print("Disconnected from Muse S")

if __name__ == "__main__":
    main()