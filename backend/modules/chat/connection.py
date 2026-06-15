from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Maps user_id (string) to a list of active WebSockets.
        # This allows a user to be connected on their phone and web browser simultaneously.
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        """Accepts the connection and registers the user's device."""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
            
        self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected. Active devices: {len(self.active_connections[user_id])}")

    def disconnect(self, websocket: WebSocket, user_id: str):
        """Removes the device when the user closes the app or loses WiFi."""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            
            # If they closed their last active device, remove them from the dictionary entirely to save RAM
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                
        logger.info(f"User {user_id} disconnected.")

    async def send_personal_message(self, message_payload: dict, receiver_id: str):
        """Pushes a live JSON message to every active device the receiver currently has open."""
        if receiver_id in self.active_connections:
            for connection in self.active_connections[receiver_id]:
                await connection.send_json(message_payload)

# We create a single, global instance of this manager so the entire app shares the same traffic controller.
manager = ConnectionManager()