import json
import logging
from typing import List, Dict, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketNotificationManager:
    """
    Real-Time WebSocket Hub.
    Manages client WebSocket connections and broadcasts live match events, score updates,
    and generated social media posts to all connected web clients and agent subscribers.
    """

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, topic: str, data: Dict[str, Any]):
        """Broadcast structured JSON message to all active WebSocket listeners."""
        if not self.active_connections:
            return

        payload = json.dumps({
            "topic": topic,
            "data": data
        }, default=str)

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"Error sending to WebSocket client: {e}")
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)
