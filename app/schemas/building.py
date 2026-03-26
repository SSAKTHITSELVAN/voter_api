from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import OrmBase


class BuildingCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    address_text: str | None = None
    total_floors: int | None = Field(None, ge=1, le=200)


class BuildingRead(OrmBase):
    id: UUID
    name: str
    address_text: str | None
    total_floors: int | None
    created_by: UUID | None
    created_at: datetime


class UnitCreate(BaseModel):
    building_id: UUID
    flat_number: str = Field(..., min_length=1, max_length=30)
    floor_number: int | None = Field(None, ge=0, le=200)


class UnitRead(OrmBase):
    id: UUID
    building_id: UUID
    flat_number: str
    floor_number: int | None
    created_at: datetime
