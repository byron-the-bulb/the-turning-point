import os
import sys
import json
import time
from subprocess import Popen
import runpod
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("/app/sphinx_bot.log", level="DEBUG", rotation="100 MB")

class SphinxBotHandler:
    def __init__(self):
        self.server_process = None
        logger.info("Sphinx Bot handler initialized")
    
    def start_server(self, daily_room_url, daily_token):
        """Start the FastAPI server with the given room details"""
        if self.server_process:
            logger.warning("Server already running, stopping it first")
            self.stop_server()
        
        # Set environment variables for the server
        env = os.environ.copy()
        env["DAILY_ROOM_URL"] = daily_room_url
        env["DAILY_TOKEN"] = daily_token
        
        # Start the server process
        logger.info(f"Starting server with Daily room: {daily_room_url}")
        self.server_process = Popen(
            ["python3", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"],
            env=env
        )
        
        # Wait a moment for the server to start
        time.sleep(2)
        if self.server_process.poll() is not None:
            logger.error("Server failed to start")
            return False
        
        logger.info("Server started successfully")
        return True
    
    def stop_server(self):
        """Stop the running server process"""
        if self.server_process:
            logger.info("Stopping server")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except:
                logger.warning("Server did not terminate gracefully, forcing")
                self.server_process.kill()
            
            self.server_process = None
            logger.info("Server stopped")
    
    def handler(self, event):
        """Main handler for RunPod serverless requests"""
        logger.info(f"Received event: {event}")
        
        try:
            # Extract input data
            input_data = event.get("input", {})
            
            # Validate required fields
            if "daily_room_url" not in input_data or "daily_token" not in input_data:
                return {
                    "error": "Missing required fields: daily_room_url and daily_token"
                }
            
            # Start the server with the provided room details
            success = self.start_server(
                input_data["daily_room_url"],
                input_data["daily_token"]
            )
            
            if not success:
                return {
                    "error": "Failed to start Sphinx Bot server"
                }
            
            # Return success response
            return {
                "status": "running",
                "message": "Sphinx Bot connected to Daily room"
            }
            
        except Exception as e:
            logger.exception("Error in handler")
            return {
                "error": str(e)
            }
    
    def cleanup(self):
        """Cleanup resources when pod is shutting down"""
        logger.info("Cleaning up resources")
        self.stop_server()

# Initialize the handler
bot_handler = SphinxBotHandler()

# Register RunPod handlers
runpod.serverless.start({
    "handler": bot_handler.handler,
    "cleanup": bot_handler.cleanup
})
