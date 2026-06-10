from pydantic import BaseModel, Field, EmailStr

class ChangePasswordRequest(BaseModel):
    """Payload for updating a user's password securely."""
    current_password: str = Field(..., min_length=8, description="Required to verify identity")
    # max_length=72 protects the bcrypt library, just like in auth
    new_password: str = Field(..., min_length=8, max_length=72)

class ChangeEmailRequest(BaseModel):
    """Payload for updating the core account email."""
    new_email: EmailStr
    password: str = Field(..., description="Required to authorize the email change")

class AccountDeleteRequest(BaseModel):
    """Payload for permanently deleting an account."""
    password: str = Field(..., description="Required to authorize account deletion")

class AccountSettingsResponse(BaseModel):
    """The private account data returned to the user."""
    id: str
    username: str
    email: EmailStr
    is_verified: bool
    is_private: bool = False
    # I might add fields like 'two_factor_enabled' or 'created_at' here later

class PrivacySettingsUpdate(BaseModel):
    """Payload for toggling account privacy."""
    is_private: bool = Field(..., description="Set to True to make account private")

