#!/bin/bash

# Define the config file path (adjust if needed)
CONFIG_FILE="/root/.runpodctl/config"

# Check if the config file exists; if not, configure it
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Config file not found, configuring runpodctl..."
    
    # Use the API key from an environment variable (e.g., RUNPOD_API_KEY)
    if [ -z "$RUNPOD_API_KEY" ]; then
        echo "Error: RUNPOD_API_KEY environment variable is not set."
        exit 1
    fi
    
    runpodctl config --apiKey="$RUNPOD_API_KEY"
    if [ $? -eq 0 ]; then
        echo "runpodctl configured successfully."
    else
        echo "Failed to configure runpodctl."
        exit 1
    fi
else
    echo "Config file found, proceeding..."
fi

# Stop the pod using the pod ID from an environment variable (e.g., RUNPOD_POD_ID)
if [ -z "$RUNPOD_POD_ID" ]; then
    echo "Error: RUNPOD_POD_ID environment variable is not set."
    exit 1
fi

runpodctl stop pod "$RUNPOD_POD_ID"
if [ $? -eq 0 ]; then
    echo "Pod $RUNPOD_POD_ID stopped successfully."
else
    echo "Failed to stop pod $RUNPOD_POD_ID."
    exit 1
fi
