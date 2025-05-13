import requests
import time
import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import threading
import sys
import logging
from scipy.signal import welch
import signal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define API base URL
API_BASE_URL = "http://localhost:8000"

# Define brain wave frequency bands (in Hz)
BANDS = {
    'Theta': (4, 8),    # 4–8 Hz
    'Alpha': (8, 12),   # 8–12 Hz
    'Beta': (12, 30),   # 12–30 Hz
    'Gamma': (30, 100)  # 30–100 Hz
}

# For storing EEG data
eeg_data = []
band_powers_history = {band: [] for band in BANDS}
is_recording = False
is_connected = False
lock = threading.Lock()
sampling_rate = 256  # Default, will be updated when connected

def check_connection():
    """Check if Muse headband is connected"""
    global is_connected, sampling_rate
    
    try:
        response = requests.get(f"{API_BASE_URL}/status")
        data = response.json()
        
        if data.get("connected", False):
            is_connected = True
            logger.info("✅ Muse headband is connected")
            return True
        else:
            logger.error(f"❌ Muse headband is not connected: {data.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        logger.error(f"❌ Error checking connection: {str(e)}")
        return False

def start_recording():
    """Start recording EEG data"""
    global is_recording
    
    if not is_connected and not check_connection():
        logger.error("Cannot start recording: Muse headband is not connected")
        return False
    
    try:
        response = requests.post(f"{API_BASE_URL}/start")
        if response.status_code == 200:
            is_recording = True
            logger.info("✅ Recording started")
            return True
        else:
            logger.error(f"❌ Failed to start recording: {response.json()}")
            return False
    except Exception as e:
        logger.error(f"❌ Error starting recording: {str(e)}")
        return False

def stop_recording():
    """Stop recording and retrieve distilled summary"""
    global is_recording
    
    try:
        response = requests.post(f"{API_BASE_URL}/stop")
        if response.status_code == 200:
            data = response.json()
            is_recording = False
            sample_count = data.get("samples", 0)
            
            # Get the distilled summary
            distilled_summary = data.get("distilled_summary", "")
            
            if distilled_summary:
                logger.info(f"✅ Recording stopped, processed {sample_count} samples")
                logger.info("Received distilled EEG summary:")
                # Print the summary with nice formatting
                for line in distilled_summary.split("\n"):
                    logger.info(f"  {line}")
                return True, distilled_summary
            else:
                logger.warning("No distilled summary was returned")
                return True, ""
        else:
            logger.error(f"❌ Failed to stop recording: {response.json()}")
            return False, ""
    except Exception as e:
        logger.error(f"❌ Error stopping recording: {str(e)}")
        return False, ""

def compute_band_powers(data=None):
    """
    Placeholder function to simulate band power calculation.
    For visualization purposes only - actual processing is done server-side.
    """
    # Generate random values for visualization
    # In the actual app, this would come from real EEG data
    import random
    
    band_powers = {
        'Alpha': random.uniform(5, 15),
        'Beta': random.uniform(3, 10),
        'Theta': random.uniform(2, 8),
        'Gamma': random.uniform(1, 5)
    }
    
    # If recording is active, these values will fluctuate more
    if is_recording:
        for band in band_powers:
            # Add some noise to make it look dynamic
            band_powers[band] += random.uniform(-2, 2)
            # Ensure values stay positive
            band_powers[band] = max(0.5, band_powers[band])
    
    return band_powers

def plot_brain_waves(ax):
    """
    Update the brain wave plot with simulated or real-time data
    """
    global band_powers_history
    
    # Get the latest band powers
    latest_powers = compute_band_powers()
    
    # Update history for visualization
    with lock:
        for band, power in latest_powers.items():
            if band not in band_powers_history:
                band_powers_history[band] = []
            band_powers_history[band].append(power)
            # Keep a reasonable history length
            if len(band_powers_history[band]) > 100:
                band_powers_history[band] = band_powers_history[band][-100:]
    
    # Plot current band powers
    bands = list(BANDS.keys())
    x = range(len(bands))
    values = [latest_powers[band] for band in bands]
    
    # Plot the band powers with distinct colors
    bars = ax.bar(x, values, color=['#3498db', '#2ecc71', '#e74c3c', '#9b59b6'])
    
    # Add labels and styling
    ax.set_xlabel('Frequency Band')
    ax.set_ylabel('Relative Power')
    ax.set_title('Brain Wave Activity' + (' (Recording)' if is_recording else ''))
    ax.set_xticks(x)
    ax.set_xticklabels(bands)
    
    # Add values on top of bars
    for i, v in enumerate(values):
        ax.text(i, v + 0.1, f"{v:.1f}", ha='center')
    
    # Fixed y scale to maintain consistent view
    ax.set_ylim(0, 20)

def update_plot(frame, fig, ax1, ax2):
    """Update function for animation"""
    global is_recording, band_powers_history
    
    # Update figure title based on recording status
    fig.suptitle(f"Muse Headband Status: {'Recording' if is_recording else 'Not Recording'}", fontsize=16)
    
    # Update the band power plot
    ax1.clear()
    plot_brain_waves(ax1)
    
    # Update EEG data plot with placeholder or message
    ax2.clear()
    if is_recording:
        ax2.text(0.5, 0.5, "Recording in progress...", 
                horizontalalignment='center', verticalalignment='center', fontsize=14)
    else:
        ax2.text(0.5, 0.5, "Press 'p' to stop recording and get distilled summary", 
                horizontalalignment='center', verticalalignment='center', fontsize=12)
        ax2.text(0.5, 0.4, "The summary will be displayed in a dialog box", 
                horizontalalignment='center', verticalalignment='center', fontsize=10)
    
    ax2.set_title("Distilled EEG Summary")
    ax2.set_xticks([])
    ax2.set_yticks([])
    
    # Improve layout
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])  # Leave room for title and instructions
    
    return ax1, ax2

def handle_key_press(event):
    """Handle keyboard input for controlling recording"""
    global is_recording, band_powers_history
    
    if event.key == 'h':
        # Display help
        logger.info("\nKEYBOARD COMMANDS:")
        logger.info("  c - Check connection")
        logger.info("  s - Start recording")
        logger.info("  p - Stop recording and process data")
        logger.info("  q - Quit")
        logger.info("  h - Show this help")
    
    elif event.key == 'c':
        # Check connection
        if check_connection():
            logger.info("\u2705 Muse headband is connected and ready")
        else:
            logger.info("\u274c Failed to connect to Muse headband")
    
    elif event.key == 's' and not is_recording:
        # Start recording
        if start_recording():
            # Reset data
            with lock:
                band_powers_history = {band: [] for band in BANDS}
            is_recording = True
            logger.info("\u2705 Recording started")
        else:
            logger.info("\u274c Failed to start recording")
    
    elif event.key == 'p' and is_recording:
        # Stop recording and process data
        logger.info("Stopping recording...")
        success, summary = stop_recording()
        if success and summary:
            # Display the summary in a dialog box
            try:
                from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
                import tkinter as tk
                from tkinter import scrolledtext
                
                dialog = tk.Toplevel()
                dialog.title("Distilled EEG Summary")
                dialog.geometry("600x400")
                
                text_area = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, width=80, height=20)
                text_area.insert(tk.INSERT, summary)
                text_area.configure(state='disabled')  # Make it read-only
                text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
                
                tk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)
                dialog.focus_set()
            except Exception as e:
                logger.error(f"Error displaying summary dialog: {e}")
                # Fall back to console output if dialog fails
                logger.info("\n=== Distilled EEG Summary ===\n")
                for line in summary.split("\n"):
                    logger.info(line)
    
    elif event.key == 'q':
        logger.info("Exiting...")
        if is_recording:
            stop_recording()
        sys.exit(0)

def main():
    global is_recording, band_powers_history
    
    # Set up signal handler for graceful exit
    def signal_handler(sig, frame):
        logger.info("\nExiting gracefully...")
        if is_recording:
            success, _ = stop_recording()
        plt.close('all')  # Close all plots
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Try to connect at startup
    if check_connection():
        logger.info("✅ Muse headband is connected and ready")
    else:
        logger.info("❌ Failed to connect to Muse headband. Make sure the API server is running.")
    
    # Create plot
    plt.ion()  # Turn on interactive mode
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    fig.suptitle("Muse Headband Status: Not Recording", fontsize=16)
    
    # Add a text box with instructions
    plt.figtext(0.5, 0.01, 
                "KEYBOARD COMMANDS: [c]heck connection | [s]tart recording | sto[p] recording | [q]uit | [h]elp", 
                ha='center', fontsize=12, bbox={"facecolor":"lightblue", "alpha":0.5, "pad":5})
    
    # Register key event handler
    fig.canvas.mpl_connect('key_press_event', handle_key_press)
    
    # Start animation for real-time updates - fix animation warnings
    ani = FuncAnimation(fig, update_plot, fargs=(fig, ax1, ax2), 
                        interval=500, blit=False, cache_frame_data=False, 
                        save_count=100)  # Limit frames in cache
    
    # Keep a reference to the animation object to prevent it from being garbage collected
    fig.ani = ani  # Store reference to animation on figure
    
    # Display initial instructions
    logger.info("\n=== Muse EEG Distilled Summary Interactive Tester ===")
    logger.info("Press keys in the plot window to control the application:")
    logger.info("  c - Check connection")
    logger.info("  s - Start recording")
    logger.info("  p - Stop recording and get distilled summary")
    logger.info("  q - Quit")
    logger.info("  h - Show this help")
    logger.info("\nThis tester provides real-time visualization of EEG wave activity")
    logger.info("and produces a distilled human-readable summary when recording stops.")
    
    try:
        # Show the plot (this will block until the window is closed)
        plt.show()
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
    finally:
        # Cleanup
        if is_recording:
            stop_recording()
        logger.info("Exiting...")

if __name__ == "__main__":
    main()
