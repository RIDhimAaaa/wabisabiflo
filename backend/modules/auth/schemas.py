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

# ---------------------------------------
# 2. Authentication / Token Schemas
# ---------------------------------------
class Token(BaseModel):
    """The JSON response sent back upon successful login."""
    access_token: str
    token_type: str = "bearer"
    # Note: We do NOT include the refresh token here because 
    # it is securely injected directly into an HttpOnly cookie.

class TokenData(BaseModel):
    """The shape of the data encoded inside our JWTs."""
    username: str | None = None