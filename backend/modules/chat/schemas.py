from pydantic import BaseModel, Field
from datetime import datetime

class MessageCreate(BaseModel):
    """The tiny payload the frontend sends when a user hits 'Send'"""
    receiver_id: str
    content: str = Field(..., max_length=1000)

class MessageResponse(BaseModel):
    """The full payload the server saves to the DB and pushes to the receiver"""
    id: str
    sender_id: str
    receiver_id: str
    content: str
    created_at: datetime
    is_read: bool = False