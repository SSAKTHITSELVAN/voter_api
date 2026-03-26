from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    phone: str = Field(..., examples=["9876543210"])
    password: str = Field(..., min_length=6, examples=["MyP@ss123"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
