#!/usr/bin/env python3
"""
Muse EEG API Tester - Distilled Summary Version

This tester focuses on recording EEG data and displaying the distilled summary
processed by the server side. It provides a simple command-line interface.
"""

import requests
import time
import sys
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API base URL
API_BASE_URL = "http://localhost:8000"

def check_connection():
    """Check if Muse headband is connected via the API"""
    try:
        response = requests.get(f"{API_BASE_URL}/status")
        data = response.json()
        
        if data.get("connected", False):
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
    try:
        response = requests.post(f"{API_BASE_URL}/start")
        if response.status_code == 200:
            logger.info("✅ Recording started")
            return True
        else:
            logger.error(f"❌ Failed to start recording: {response.json()}")
            return False
    except Exception as e:
        logger.error(f"❌ Error starting recording: {str(e)}")
        return False

def stop_recording(save_to_file=None):
    """Stop recording and get distilled summary"""
    try:
        response = requests.post(f"{API_BASE_URL}/stop")
        if response.status_code == 200:
            data = response.json()
            sample_count = data.get("samples", 0)
            logger.info(f"✅ Recording stopped, processed {sample_count} samples")
            
            # Get the distilled summary
            distilled_summary = data.get("distilled_summary", "")
            
            if distilled_summary:
                # Print the summary with nice formatting
                print("\n=== Distilled EEG Summary ===\n")
                for line in distilled_summary.split("\n"):
                    print(f"{line}")
                
                # Save to file if requested
                if save_to_file:
                    with open(save_to_file, 'w') as f:
                        f.write(distilled_summary)
                    print(f"\nSummary saved to {save_to_file}")
                
                return distilled_summary
            else:
                logger.warning("No distilled summary was returned")
                return ""
        else:
            logger.error(f"❌ Failed to stop recording: {response.json()}")
            return ""
    except Exception as e:
        logger.error(f"❌ Error stopping recording: {str(e)}")
        return ""

def record_for_duration(duration, output_file=None):
    """Record EEG data for the specified duration and get summary"""
    if not check_connection():
        logger.error("Cannot start recording: Muse headband is not connected")
        return ""
    
    if not start_recording():
        logger.error("Failed to start recording")
        return ""
    
    print(f"Recording for {duration} seconds...")
    try:
        # Display a countdown
        for i in range(duration, 0, -1):
            sys.stdout.write(f"\rTime remaining: {i} seconds...")
            sys.stdout.flush()
            time.sleep(1)
        print("\nRecording complete. Processing data...")
    except KeyboardInterrupt:
        print("\nRecording interrupted by user")
    
    # Stop recording and get the summary
    return stop_recording(output_file)

def interactive_mode():
    """Interactive recording session"""
    print("\n=== Muse EEG Distilled Summary Tester ===")
    
    # Check connection first
    print("Checking connection to Muse headband...")
    if not check_connection():
        print("Failed to connect to Muse headband. Make sure the API server is running.")
        return
    
    # Ask user for recording duration
    try:
        print("\nHow long would you like to record EEG data?")
        duration_str = input("Enter duration in seconds (default: 30): ").strip()
        duration = int(duration_str) if duration_str else 30
        
        # Ask if they want to save the output
        save_str = input("Save summary to file? (y/n, default: n): ").strip().lower()
        save_file = None
        if save_str == 'y' or save_str == 'yes':
            filename = input("Enter filename (default: eeg_summary.txt): ").strip()
            save_file = filename if filename else f"eeg_summary_{int(time.time())}.txt"
        
        # Record for the specified duration
        record_for_duration(duration, save_file)
        
    except KeyboardInterrupt:
        print("\nSession interrupted by user")
    except ValueError:
        print("Invalid duration. Please enter a number of seconds.")
    except Exception as e:
        print(f"Error: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description="Test the Muse EEG API and get distilled summaries")
    
    # Add subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Check connection
    check_parser = subparsers.add_parser("check", help="Check if Muse headband is connected")
    
    # Record for duration
    record_parser = subparsers.add_parser("record", help="Record EEG data for specified duration")
    record_parser.add_argument("duration", type=int, help="Duration in seconds")
    record_parser.add_argument("-o", "--output", help="File to save the distilled summary")
    
    # Interactive mode
    interactive_parser = subparsers.add_parser("interactive", help="Interactive recording session")
    
    args = parser.parse_args()
    
    # Default to interactive mode if no command is specified
    if not args.command:
        interactive_mode()
        return
    
    # Execute the requested command
    if args.command == "check":
        check_connection()
    elif args.command == "record":
        record_for_duration(args.duration, args.output)
    elif args.command == "interactive":
        interactive_mode()

if __name__ == "__main__":
    main()
