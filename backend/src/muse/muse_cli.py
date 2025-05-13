#!/usr/bin/env python3
"""
Muse EEG API Command Line Client

This script provides a simple command-line interface to interact with the Muse EEG REST API.
It can be used to check connection status, start/stop recording, and retrieve EEG data.
"""

import argparse
import requests
import json
import sys
import time
import os

# API base URL
API_BASE_URL = "http://localhost:8000"

def check_connection():
    """Check if Muse headband is connected"""
    try:
        response = requests.get(f"{API_BASE_URL}/status")
        data = response.json()
        
        if data.get("connected", False):
            print("✅ Muse headband is connected")
            return 0
        else:
            print(f"❌ Muse headband is not connected: {data.get('error', 'Unknown error')}")
            return 1
    except Exception as e:
        print(f"❌ Error checking connection: {str(e)}")
        return 1

def start_recording():
    """Start recording EEG data"""
    try:
        response = requests.post(f"{API_BASE_URL}/start")
        if response.status_code == 200:
            print("✅ Recording started")
            return 0
        else:
            print(f"❌ Failed to start recording: {response.json()}")
            return 1
    except Exception as e:
        print(f"❌ Error starting recording: {str(e)}")
        return 1

def stop_recording(output_file=None):
    """Stop recording and retrieve distilled summary"""
    try:
        response = requests.post(f"{API_BASE_URL}/stop")
        if response.status_code == 200:
            data = response.json()
            sample_count = data.get("samples", 0)
            print(f"✅ Recording stopped, processed {sample_count} samples")
            
            # Get the distilled summary
            distilled_summary = data.get("distilled_summary", "")
            
            if distilled_summary:
                print("\n=== Distilled EEG Summary ===\n")
                # Print with nice formatting
                for line in distilled_summary.split("\n"):
                    print(f"{line}")
                
                # If output file is specified, save the summary
                if output_file:
                    with open(output_file, 'w') as f:
                        f.write(distilled_summary)
                    print(f"\n✅ Summary saved to {output_file}")
            else:
                print("\nNo distilled summary was returned. Recording may have been too short.")
            
            return 0
        else:
            print(f"❌ Failed to stop recording: {response.json()}")
            return 1
    except Exception as e:
        print(f"❌ Error stopping recording: {str(e)}")
        return 1

def record_for_duration(duration, output_file=None):
    """Record for a specific duration in seconds"""
    result = start_recording()
    if result != 0:
        return result
    
    print(f"Recording for {duration} seconds...")
    try:
        # Display a simple progress bar
        for i in range(duration):
            remaining = duration - i
            bar_length = 40
            progress = int((i / duration) * bar_length)
            bar = '█' * progress + '░' * (bar_length - progress)
            sys.stdout.write(f"\r[{bar}] {i}/{duration}s")
            sys.stdout.flush()
            time.sleep(1)
        print("\nRecording complete!")
    except KeyboardInterrupt:
        print("\nRecording interrupted by user")
    
    return stop_recording(output_file)

def main():
    parser = argparse.ArgumentParser(description="Muse EEG API command-line client")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check if Muse headband is connected")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start recording EEG data")
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop recording and retrieve data")
    stop_parser.add_argument("-o", "--output", help="Output file to save EEG data (JSON format)")
    
    # Record command
    record_parser = subparsers.add_parser("record", help="Record for a specific duration")
    record_parser.add_argument("duration", type=int, help="Duration in seconds")
    record_parser.add_argument("-o", "--output", help="Output file to save EEG data (JSON format)")
    
    args = parser.parse_args()
    
    if args.command == "status":
        return check_connection()
    elif args.command == "start":
        return start_recording()
    elif args.command == "stop":
        return stop_recording(args.output)
    elif args.command == "record":
        return record_for_duration(args.duration, args.output)
    else:
        parser.print_help()
        return 0

if __name__ == "__main__":
    sys.exit(main())
