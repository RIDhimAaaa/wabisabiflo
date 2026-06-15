from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from .schemas import MessageResponse

class ChatService:
    @staticmethod
    async def save_message(
        sender_id: str,
        receiver_id: str,
        content: str,
        db: AsyncIOMotorDatabase
    ) -> MessageResponse:
        """
        Saves a new message to MongoDB and returns the formatted response
        ready to be fired over the WebSocket connection.
        """
        message_doc = {
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "content": content,
            "created_at": datetime.now(timezone.utc),
            "is_read": False
        }

        result = await db.messages.insert_one(message_doc)

        return MessageResponse(
            id=str(result.inserted_id),
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content,
            created_at=message_doc["created_at"],
            is_read=False
        )

    @staticmethod
    async def get_chat_history(
        user_a_id: str,
        user_b_id: str,
        db: AsyncIOMotorDatabase,
        limit: int = 50,
        cursor: str | None = None
    ) -> dict:
        """
        Fetches the chronological chat history between two users using Cursor Pagination.
        """
        # 1. The Interleaved Query: Find messages where A sent to B, OR B sent to A.
        query = {
            "$or": [
                {"sender_id": user_a_id, "receiver_id": user_b_id},
                {"sender_id": user_b_id, "receiver_id": user_a_id}
            ]
        }

        if cursor:
            # Fetch messages strictly older than the cursor (when the user scrolls UP in the chat)
            query["_id"] = {"$lt": ObjectId(cursor)}

        # 2. Sort by _id descending to grab the most recent cluster of messages
        db_cursor = db.messages.find(query).sort("_id", -1).limit(limit + 1)
        messages = await db_cursor.to_list(length=limit + 1)

        next_cursor = None
        if len(messages) > limit:
            extra_message = messages.pop()
            next_cursor = str(extra_message["_id"])

        # 3. The UI Flip
        # We pulled them newest-first to get the recent batch, but chat UIs 
        # expect messages to be rendered oldest-at-the-top to newest-at-the-bottom.
        messages.reverse()

        formatted_messages = [
            MessageResponse(
                id=str(msg["_id"]),
                sender_id=msg["sender_id"],
                receiver_id=msg["receiver_id"],
                content=msg["content"],
                created_at=msg["created_at"],
                is_read=msg.get("is_read", False)
            ) for msg in messages
        ]

        return {
            "items": formatted_messages,
            "next_cursor": next_cursor
        }

    @staticmethod
    async def mark_messages_as_read(
        sender_id: str,
        receiver_id: str,
        db: AsyncIOMotorDatabase
    ):
        """
        When a user opens a chat room, instantly mark all unread messages 
        sent BY the other person to THIS user as read.
        """
        result = await db.messages.update_many(
            {
                "sender_id": sender_id,     # The person who sent the texts
                "receiver_id": receiver_id, # The person opening the app right now
                "is_read": False
            },
            {"$set": {"is_read": True}}
        )

        return {"updated_count": result.modified_count}
    
    
    @staticmethod
    async def process_live_message(
        raw_text: str,
        sender_id: str,
        db: AsyncIOMotorDatabase,
        manager: any  # Passing the connection manager via dependency injection
    ):
        """
        The orchestrator for live WebSockets. 
        Parses, validates, saves to MongoDB, and broadcasts the message.
        """
        # 1. Parse and Validate
        data = json.loads(raw_text)
        message_in = MessageCreate(**data)
        
        # 2. Persistence: Save to DB
        saved_message = await ChatService.save_message(
            sender_id=sender_id,
            receiver_id=message_in.receiver_id,
            content=message_in.content,
            db=db
        )
        
        # 3. Format for the wire
        payload = {
            "id": saved_message.id,
            "sender_id": saved_message.sender_id,
            "receiver_id": saved_message.receiver_id,
            "content": saved_message.content,
            "created_at": saved_message.created_at.isoformat(),
            "is_read": saved_message.is_read
        }

        # 4. Flight: Broadcast to both parties
        await manager.send_personal_message(payload, message_in.receiver_id)
        await manager.send_personal_message(payload, sender_id)