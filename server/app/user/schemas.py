import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)


class UserCreate(UserBase):
    username: str = Field(..., min_length=3, max_length=32, pattern="^[a-zA-Z0-9_]+$")
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    password: Optional[str] = Field(None, min_length=8, max_length=128)


class UserRead(UserBase):
    id: uuid.UUID
    username: str
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    # Included in development/testing for UI convenience; set to None once verified
    verification_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
