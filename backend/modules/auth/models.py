from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class UserInDB(BaseModel):
    username: str
    email: EmailStr
    hashed_password: str
    is_verified: bool = False
    is_celebrity: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)