# Sphinx Voice Bot RunPod Container

This directory contains the Docker configuration for deploying the Sphinx Voice Bot on RunPod.

## Overview

The container provides:
- FastAPI server for Sphinx Voice Bot
- Pipecat SDK integration with modern PipelineRunner pattern
- Hume AI Emotion Analysis via WebSocket streaming
- Daily.co video/audio integration

## Environment Variables

The container requires the following environment variables:

- `DAILY_ROOM_URL` - URL of the Daily.co room to join
- `DAILY_TOKEN` - Token for authenticating with Daily.co
- `HUME_API_KEY` (optional) - API key for Hume AI emotion analysis

## Usage

### Building the Container

```bash
./build.sh
```

### Testing Locally

```bash
docker run -p 8000:8000 \
  -e DAILY_ROOM_URL="https://your-domain.daily.co/room-name" \
  -e DAILY_TOKEN="your-daily-token" \
  -e HUME_API_KEY="your-hume-api-key" \
  sphinx-voice-bot:latest
```

### Deploying to RunPod

1. Push the image to a container registry
2. Create a RunPod template using this image
3. Use the RunPod API to start pods with the required environment variables

## Components

- `emotion_analyzer.py` - Uses Hume AI SDK for real-time emotion analysis
- `voice_processor.py` - Uses Pipecat SDK for audio processing
- `server.py` - FastAPI server integrating both components
- `runpod_handler.py` - Handles RunPod serverless requests
- `start.sh` - Container entrypoint script

## Logging

Logs are available at `/app/sphinx_bot.log` inside the container.
