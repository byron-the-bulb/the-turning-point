# Sphinx Voice Bot

A voice-based conversational AI bot that provides guided conversations with real-time emotion analysis and feedback.

## Overview

Sphinx Voice Bot is a sophisticated conversational AI platform built on a modern architecture that combines real-time audio processing, emotion analysis, and guided conversation flows. The bot can be deployed as a Docker container and connects to users through Daily.co video/audio rooms.

## Installation and Usage

### Prerequisites

- Docker with NVIDIA support (for GPU acceleration)
- NVIDIA CUDA 12.1 compatible GPU (recommended for optimal performance)
- AWS account (optional, for CloudWatch logging)
- API keys for:
  - Daily.co
  - OpenAI
  - Hume AI (for emotion analysis)

### Building the Docker Image

The project includes a Dockerfile in the `backend` directory. To build the image:

```bash
cd backend
./build.sh
```

Alternatively, you can build manually:

```bash
cd backend
docker build -t sphinx-voice-bot .
```

The build process:
1. Uses NVIDIA CUDA 12.1 base image
2. Installs system dependencies including Python 3.10, ffmpeg, and CUDA libraries
3. Installs Python dependencies from requirements.txt
4. Downloads and caches the Whisper medium model
5. Configures the application entrypoint

### Running the Server Locally

#### Without Docker

1. Set up a Python virtual environment:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Run the FastAPI server:

```bash
cd src/sphinx-bot
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

use the connect_local api nextjs endpoint when running locally with the FastAPI server
in `.env.local` of frontend-next change the endpoint to connect to the local server:
```
NEXT_PUBLIC_API_ENDPOINT=/connect_local
```

#### With Docker

```bash
docker run -p 8000:8000 \
  --gpus all \
  -e DAILY_API_KEY=your_daily_api_key \
  -e OPENAI_API_KEY=your_openai_api_key \
  -e HUME_API_KEY=your_hume_api_key \
  sphinx-voice-bot
```

### Example .env File

Create a `.env` file in the `backend/src/sphinx-bot` directory with the following content:

```
# API Keys
DAILY_API_KEY=your_daily_api_key
OPENAI_API_KEY=your_openai_api_key
HUME_API_KEY=your_hume_api_key

# Daily.co Configuration
# Optional: Use these for testing with a persistent room
# DAILY_SAMPLE_ROOM_URL=https://your-domain.daily.co/your-room
# DAILY_SAMPLE_ROOM_TOKEN=your_daily_room_token

# AWS Configuration (for CloudWatch logging)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
CLOUDWATCH_LOG_GROUP=/sphinx-voice-bot

# Whisper STT Configuration
SPHINX_WHISPER_DEVICE=cuda  # Options: cuda, cpu
```

## Logging

The application uses a multi-layered logging approach:

1. **Console Logging**: All logs are output to the console using Loguru
2. **CloudWatch Logging**: When AWS credentials are provided, logs are also sent to AWS CloudWatch

CloudWatch logging features:
- Automatic creation of log groups and streams
- Unique stream names based on bot instance IDs
- Error handling with automatic retries for sequence token issues
- Batched log submission for efficiency

To access CloudWatch logs:
1. Log in to the AWS Management Console
2. Navigate to CloudWatch > Log groups > `/sphinx-voice-bot` (or your custom log group)
3. Select the log stream for your bot instance

## Architecture and Code

### High-Level Architecture

The Sphinx Voice Bot consists of these main components:

1. **FastAPI Server** (`server.py`): Manages bot instances and provides endpoints for:
   - Direct browser access (`GET /`)
   - RTVI client connections (`POST /connect`)
   - Status monitoring (`GET /status/{pid}`)

2. **Voice Bot Implementation** (`sphinx_bot.py`): Implements the conversational AI using:
   - Pipecat Pipeline for audio processing
   - Custom RTVIProcessor for real-time voice interaction
   - Daily.co for audio/video transport
   - Integration with STT, TTS, and LLM services

3. **Conversation Flow Management**: Uses the Pipecat Flows framework to manage:
   - Conversation nodes and paths
   - User interaction handling
   - Context preservation between turns

### How Bots Work

Each bot instance is:

1. **Dynamically Spawned**: When a user connects to the server, a new bot process is created
2. **Independently Managed**: Each bot runs in its own process with a unique identifier
3. **Room-Specific**: Each bot is tied to a specific Daily room URL and token
4. **Stateful**: Bots maintain conversation state during a session

Bot lifecycle:
1. User connects to `/` or `/connect` endpoint
2. Server creates a Daily.co room (or uses provided sample room)
3. Server generates access token
4. Server spawns a new bot subprocess with the room URL and token
5. User is connected to the bot in the Daily room
6. Bot manages the conversation using the Pipecat pipeline
7. Process terminates when the user disconnects or session times out

### Key Dependencies

1. **Pipecat SDK** (v0.0.62):
   - Provides the pipeline architecture for audio processing
   - Handles real-time voice interaction
   - Integrates STT, TTS, and LLM services

2. **Hume AI SDK** (v0.7.13):
   - Provides real-time emotion analysis
   - Uses WebSocket streaming for continuous processing

3. **Daily.co SDK**:
   - Handles audio/video transport
   - Manages room creation and participant connections

4. **OpenAI Services**:
   - GPT-4o for language model capabilities
   - Whisper for speech-to-text transcription

5. **FastAPI and Uvicorn**:
   - Provides the web server framework
   - Handles HTTP and WebSocket connections

## Development

### Project Structure

```
sphinx-voice-bot/
├── backend/
│   ├── Dockerfile
│   ├── build.sh
│   ├── requirements.txt
│   └── src/
│       └── sphinx-bot/
│           ├── __init__.py
│           ├── cloudwatch_logger.py
│           ├── custom_flow_manager.py
│           ├── server.py
│           ├── sphinx_bot.py
│           ├── sphinx_script.py
│           └── status_utils.py
├── frontend-next/
│   └── ...
└── docs/
    └── ...
```

### Adding New Capabilities

To extend the bot's capabilities:

1. **Add new conversation flows**: Modify `sphinx_script.py` to define new conversation paths and responses
2. **Enhance emotion analysis**: Integrate additional Hume AI features or custom emotion processing logic
3. **Improve audio processing**: Add custom audio processors to the Pipecat pipeline

## Troubleshooting

Common issues and solutions:

1. **GPU Acceleration Issues**: If you encounter CUDA errors, try setting `SPHINX_WHISPER_DEVICE=cpu` in your `.env` file
2. **Daily.co Connection Problems**: Verify your Daily API key and ensure you have sufficient room credits
3. **Missing API Keys**: Check that all required API keys are properly set in your environment
4. **Bot Process Crashes**: Check the CloudWatch logs for detailed error messages
