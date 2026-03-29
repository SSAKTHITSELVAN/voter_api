from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from app.models.household import GenderType, HouseType
from app.models.record import VerificationStatus
from app.models.user import UserRole
from app.schemas.common import OrmBase


class PersonCreate(BaseModel):
    age: int | None = Field(None, ge=0, le=120)
    gender: GenderType | None = None
    is_voter: bool = False


class PersonRead(OrmBase):
    id: UUID
    household_id: UUID
    age: int | None
    gender: GenderType | None
    is_voter: bool


class HouseholdImageRead(OrmBase):
    id: UUID
    household_id: UUID
    image_url: str
    uploaded_by: UUID
    created_at: datetime


class HouseholdCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    address_text: str | None = None
    house_type: HouseType
    unit_id: UUID | None = None
    persons: list[PersonCreate] = Field(default_factory=list)
    landmark_image_urls: list[str] = Field(
        default_factory=list,
        max_length=5,
        validation_alias=AliasChoices("landmark_image_urls", "image_urls"),
    )

    @model_validator(mode="after")
    def apartment_must_have_unit(self) -> "HouseholdCreate":
        if self.house_type == HouseType.APARTMENT and self.unit_id is None:
            raise ValueError("unit_id is required for APARTMENT type households")
        if self.house_type == HouseType.INDIVIDUAL and self.unit_id is not None:
            raise ValueError("unit_id must be null for INDIVIDUAL type households")
        return self


class HouseholdRead(OrmBase):
    id: UUID
    latitude: float
    longitude: float
    address_text: str | None
    house_type: HouseType
    unit_id: UUID | None
    created_by: UUID
    created_at: datetime
    deleted_at: datetime | None
    persons: list[PersonRead] = Field(default_factory=list)
    landmark_images: list[HouseholdImageRead] = Field(default_factory=list)


class HouseholdBrief(OrmBase):
    id: UUID
    latitude: float
    longitude: float
    address_text: str | None
    house_type: HouseType
    created_at: datetime
    distance_metres: float | None = None
    landmark_image_count: int = 0
    landmark_image_url: str | None = None


class BulkHouseholdCreate(BaseModel):
    households: list[HouseholdCreate] = Field(..., min_length=1, max_length=500)


class BulkUploadResult(BaseModel):
    total: int
    created: int
    duplicates_skipped: int
    errors: list[dict] = Field(default_factory=list)


class NearbySearchParams(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    radius_metres: float = Field(500.0, ge=1.0, le=50000.0)
    limit: int = Field(50, ge=1, le=200)


class DuplicateCheckResult(BaseModel):
    has_duplicates: bool
    duplicates: list[HouseholdBrief]


class CollectionRecordRead(OrmBase):
    id: UUID
    household_id: UUID
    collected_by: UUID
    collected_by_name: str | None = None
    collected_by_phone: str | None = None
    collected_by_role: UserRole | None = None
    household_address_text: str | None = None
    household_house_type: HouseType | None = None
    household_latitude: float | None = None
    household_longitude: float | None = None
    total_people: int
    total_voters: int
    raw_data_json: dict | None
    created_at: datetime


class VerificationCreate(BaseModel):
    household_id: UUID
    status: VerificationStatus
    notes: str | None = Field(None, max_length=1000)


class VerificationRead(OrmBase):
    id: UUID
    household_id: UUID
    verified_by: UUID
    status: VerificationStatus
    notes: str | None
    created_at: datetime
