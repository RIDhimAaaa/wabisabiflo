from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
import json
import logging

from db.mongo import get_database
from dependencies.auth import get_current_user # Assuming you have a standard auth dependency
from dependencies.auth import verify_ws_token # You'll need your JWT verification function here
from .service import ChatService
from .connection import manager
from .schemas import MessageCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

# ---------------------------------------------------------
# REST API (For loading past messages)
# ---------------------------------------------------------

@router.get("/{target_id}/history")
async def fetch_chat_history(
    target_id: str,
    cursor: str | None = Query(None, description="Pagination cursor (ObjectId string)"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Fetches chronological message history between the logged-in user and a target user."""
    user_id = str(current_user["_id"])
    
    # Instantly mark incoming messages from this person as read since we just opened the chat
    await ChatService.mark_messages_as_read(sender_id=target_id, receiver_id=user_id, db=db)
    
    return await ChatService.get_chat_history(
        user_a_id=user_id, 
        user_b_id=target_id, 
        db=db, 
        limit=limit, 
        cursor=cursor
    )

@router.websocket("/ws")
async def chat_websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT Token must be passed in the URL"),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """The permanent, real-time connection."""
    
    # 1. Authenticaton using your real dependency
    try:
        user_id = verify_ws_token(token)
    except ValueError as e:
        logger.error(f"WebSocket auth failed: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, user_id)

    try:
        # The Skinny Loop
        while True:
            # 1. Listen
            raw_text = await websocket.receive_text()
            
            # 2. Hand off all business logic to the Smart Service
            await ChatService.process_live_message(raw_text, user_id, db, manager)

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)