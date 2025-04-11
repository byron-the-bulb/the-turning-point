"""
Sphinx Bot WebSocket Server using Pipecat AI
"""
import asyncio
import base64
import json
import logging
import os
from typing import Dict, List, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from sphinx_bot import SphinxBot

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI()

# Add CORS middleware to allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active connections
active_connections: Dict[str, WebSocket] = {}
# Store bot instances for each connection
bot_instances: Dict[str, SphinxBot] = {}


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    active_connections[client_id] = websocket
    bot = SphinxBot(client_id)
    bot_instances[client_id] = bot
    
    try:
        logger.info(f"Client {client_id} connected")
        
        # Send welcome message
        await websocket.send_json({
            "type": "transcript",
            "text": "Welcome! I'm your Sphinx Bot. How can I help you today?",
            "is_final": True,
        })
        
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "audio":
                # Audio data received
                audio_base64 = data.get("data", "")
                if not audio_base64:
                    continue
                    
                # Decode audio data
                audio_bytes = base64.b64decode(audio_base64)
                
                # Process the audio with the bot
                async for response in bot.process_audio(audio_bytes):
                    await websocket.send_json(response)
                    
            elif message_type == "text":
                # Text data received (for debugging or direct text input)
                text = data.get("text", "")
                if not text:
                    continue
                    
                logger.info(f"Received text message from client {client_id}: {text}")
                
                # Process the text with the bot
                response = await bot.process_text(text)
                await websocket.send_json(response)
                
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"Error processing websocket: {e}", exc_info=True)
    finally:
        # Clean up
        if client_id in active_connections:
            del active_connections[client_id]
        if client_id in bot_instances:
            await bot_instances[client_id].cleanup()
            del bot_instances[client_id]


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
