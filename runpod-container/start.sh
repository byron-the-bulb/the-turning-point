#!/bin/bash
set -e

# Define log file
LOG_FILE="/app/sphinx_bot.log"

# Print environment variables for debugging (excluding token)
echo "Starting Sphinx Voice Bot on RunPod..." | tee -a $LOG_FILE
echo "DAILY_ROOM_URL: ${DAILY_ROOM_URL}" | tee -a $LOG_FILE
echo "Daily Token is set: $(if [ -n "$DAILY_TOKEN" ]; then echo "Yes"; else echo "No"; fi)" | tee -a $LOG_FILE

# If we're running in RunPod serverless mode, use the handler
if [ "$RUNPOD_SERVERLESS" = "1" ]; then
    echo "Running in serverless mode" | tee -a $LOG_FILE
    python3 /app/runpod_handler.py
else
    # Otherwise, run the FastAPI server for direct room connectivity
    echo "Running in room connection mode with Daily.co" | tee -a $LOG_FILE
    
    # Check if required env vars are set
    if [ -z "$DAILY_ROOM_URL" ] || [ -z "$DAILY_TOKEN" ]; then
        echo "ERROR: DAILY_ROOM_URL and DAILY_TOKEN must be set" | tee -a $LOG_FILE
        exit 1
    fi
    
    # Start the FastAPI server
    echo "Starting FastAPI server..." | tee -a $LOG_FILE
    exec python3 -m uvicorn server:app --host 0.0.0.0 --port 8000
fi
