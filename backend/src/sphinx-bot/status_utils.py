"""
Simple utility for updating conversation status directly from handlers.

This avoids using frames for status updates and directly calls the API endpoint.
"""

import aiohttp
import asyncio
import os
import urllib.parse
from loguru import logger
from pipecat.processors.frameworks.rtvi import RTVIProcessor, RTVIServerMessageFrame

class StatusUpdater:
    """Simple utility for updating status without using frames."""
    
    def __init__(self):
        """Initialize the status updater."""
        self.rtvi = None
        self.identifier = None
        self.room_url = None  # Keep for backward compatibility and additional context
    
    async def initialize(self, rtvi : RTVIProcessor, identifier, room_url=None):
        """Initialize with a bot identifier and optional room URL.
        
        Args:
            identifier: Unique identifier for the bot
            room_url: Optional URL of the room (for additional context)
        """
        self.rtvi = rtvi
        self.identifier = identifier
        self.room_url = room_url
        logger.info(f"StatusUpdater initialized for identifier: {identifier}")
        if room_url:
            logger.info(f"Room URL for reference: {room_url}")
        
    async def update_status(self, status, context=None):
        """Update the status via API call.
        
        Args:
            status: Status message
            context: Additional context data (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """

        print("Updating status:", status, context)
        if not self.rtvi:
            print("StatusUpdater not initialized with RTVI processor")
            return False
            
        # Prepare the payload
        data = {
            "status": status,
            "identifier": self.identifier
        }
        
        try:
            status_frame = RTVIServerMessageFrame(data)
            await self.rtvi.push_frame(status_frame)
            return True
        except Exception as e:
            logger.error(f"Error updating status: {e}")
            return False
            

# Create a singleton instance
status_updater = StatusUpdater()
