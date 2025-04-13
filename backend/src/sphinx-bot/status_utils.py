import aiohttp
import asyncio
import os
import urllib.parse
from loguru import logger
from pipecat.processors.frameworks.rtvi import RTVIProcessor, RTVIServerMessageFrame

class StatusUpdater:
    def __init__(self):
        self.rtvi = None
        self.identifier = None
        self.room_url = None
    
    async def initialize(self, rtvi: RTVIProcessor, identifier, room_url=None):
        self.rtvi = rtvi
        self.identifier = identifier
        self.room_url = room_url
        logger.info(f"StatusUpdater initialized for identifier: {identifier}")
        if room_url:
            logger.info(f"Room URL for reference: {room_url}")
    
    async def update_status(self, status, context=None,ui_override=None):
        logger.info(f"Updating status: {status} with UI override: {ui_override}")
        if not self.rtvi:
            logger.error("StatusUpdater not initialized with RTVI processor")
            return False
        
        data = {
            "status": status,
            "identifier": self.identifier,
            "status_context": context,
            "ui_override": ui_override  # Structured UI override data
        }
        
        try:
            status_frame = RTVIServerMessageFrame(data)
            await self.rtvi.push_frame(status_frame)
            return True
        except Exception as e:
            logger.error(f"Error updating status: {e}")
            return False

    async def trigger_ui_override(self):
        logger.info("Triggering UI override")
        if not self.rtvi:
            logger.error("StatusUpdater not initialized with RTVI processor")
            return False
        
        data = {
            "trigger": "UIOverride",
            "identifier": self.identifier,
            "status_context": None,
            "ui_override": None
        }
        
        try:
            status_frame = RTVIServerMessageFrame(data)
            await self.rtvi.push_frame(status_frame)
            return True
        except Exception as e:
            logger.error(f"Error triggering UI override: {e}")
            return False

    async def close(self):
        logger.info("Sending goodbye system status")
        if not self.rtvi:
            logger.error("StatusUpdater not initialized with RTVI processor")
            return False
        
        data = {
            "status": "goodbye",
            "identifier": self.identifier,
            "status_context": None,
            "ui_override": None
        }
        
        try:
            status_frame = RTVIServerMessageFrame(data)
            await self.rtvi.push_frame(status_frame)
            return True
        except Exception as e:
            logger.error(f"Error closing StatusUpdater: {e}")
            return False


status_updater = StatusUpdater()