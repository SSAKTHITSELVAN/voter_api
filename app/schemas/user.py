from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.user import UserRole
from app.schemas.common import OrmBase


class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    phone: str = Field(..., min_length=10, max_length=15)
    password: str = Field(..., min_length=6, max_length=64)
    role: UserRole

    @field_validator("phone")
    @classmethod
    def phone_digits_only(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Phone must contain digits only")
        return v


class UserRead(OrmBase):
    id: UUID
    name: str
    phone: str
    role: UserRole
    created_by: UUID | None
    created_at: datetime
    deleted_at: datetime | None


class UserList(OrmBase):
    items: list[UserRead]
    total: int
