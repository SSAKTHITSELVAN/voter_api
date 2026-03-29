import uuid
import enum

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDMixin, TimestampMixin, SoftDeleteMixin


class HouseType(str, enum.Enum):
    INDIVIDUAL = "INDIVIDUAL"
    APARTMENT = "APARTMENT"


class GenderType(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class Household(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "households"

    # Location – plain floats, no PostGIS required
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    address_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    landmark_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    house_type: Mapped[HouseType] = mapped_column(
        Enum(HouseType, name="housetype"), nullable=False
    )

    # Apartment link (nullable for INDIVIDUAL)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("units.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationships
    creator: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", back_populates="households", foreign_keys=[created_by]
    )
    unit: Mapped["Unit | None"] = relationship(  # type: ignore[name-defined]
        "Unit", back_populates="household"
    )
    images: Mapped[list["HouseholdImage"]] = relationship(
        "HouseholdImage", back_populates="household", cascade="all, delete-orphan"
    )
    persons: Mapped[list["Person"]] = relationship(
        "Person", back_populates="household", cascade="all, delete-orphan"
    )
    collection_records: Mapped[list["CollectionRecord"]] = relationship(  # type: ignore
        "CollectionRecord", back_populates="household"
    )
    verification_records: Mapped[list["VerificationRecord"]] = relationship(  # type: ignore
        "VerificationRecord", back_populates="household"
    )

    def __repr__(self) -> str:
        return f"<Household id={self.id} lat={self.latitude} lon={self.longitude}>"

    @property
    def landmark_images(self) -> list["HouseholdImage"]:
        return self.images


class HouseholdImage(UUIDMixin, TimestampMixin, Base):
    """Max 5 images per household – enforced at service layer."""
    __tablename__ = "household_images"

    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_url: Mapped[str] = mapped_column(String(512), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    household: Mapped["Household"] = relationship("Household", back_populates="images")

    def __repr__(self) -> str:
        return f"<HouseholdImage id={self.id} household_id={self.household_id}>"


class Person(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "persons"

    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("households.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[GenderType | None] = mapped_column(
        Enum(GenderType, name="gendertype"), nullable=True
    )
    is_voter: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    household: Mapped["Household"] = relationship("Household", back_populates="persons")

    def __repr__(self) -> str:
        return f"<Person id={self.id} household_id={self.household_id} voter={self.is_voter}>"

