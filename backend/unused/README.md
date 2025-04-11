# Sphinx Voice Bot

A simple voice-based chatbot using Pipecat with WebSocket support. This bot uses OpenAI's Whisper for speech recognition, OpenAI's GPT for natural language processing, and Cartesia for text-to-speech conversion.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables:
   - Edit the `.env` file and add your API keys:
     ```
     OPENAI_API_KEY=your_openai_api_key_here
     CARTESIA_API_KEY=your_cartesia_api_key_here
     PORT=8000
     ```

## Running the Bot

1. Start the WebSocket server:
   ```bash
   python server.py
   ```

2. The server will be available at `ws://localhost:8000/ws/{client_id}` where `client_id` is a unique identifier for each client connection.

## Integration with Frontend

The bot is designed to work with the included web UI in `frontend/guide-interface`. The frontend communicates with the bot via WebSocket connections.

### WebSocket Message Format

#### From Client to Server:
- Audio data sent as binary
- Text messages sent as JSON with format: `{ "text": "your message here" }`

#### From Server to Client:
- Transcript updates: `{ "type": "transcript", "text": "transcribed text", "is_final": true }`
- Response text: `{ "type": "response", "text": "bot response", "is_final": true }`
- Audio responses: `{ "type": "audio", "data": "base64 encoded audio", "is_final": true }`

## Architecture

The bot uses Pipecat's pipeline architecture to process audio through these stages:
1. Speech recognition (OpenAI Whisper)
2. Natural language processing (OpenAI GPT)
3. Text-to-speech (Cartesia TTS)

Each component is modular and can be replaced or enhanced as needed.
