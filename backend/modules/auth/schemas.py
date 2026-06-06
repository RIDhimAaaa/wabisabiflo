from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    is_verified: bool

class Token(BaseModel):
    access_token: str
    token_type: str