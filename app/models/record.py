import uuid
import enum

from sqlalchemy import Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDMixin, TimestampMixin


class VerificationStatus(str, enum.Enum):
    MATCHED = "MATCHED"
    MISMATCH = "MISMATCH"


class CollectionRecord(UUIDMixin, TimestampMixin, Base):
    """
    Written when a Field User submits collected data for a household.
    Stores a snapshot of aggregated counts + raw JSON payload.
    """
    __tablename__ = "collection_records"

    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("households.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    collected_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    total_people: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_voters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_data_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    household: Mapped["Household"] = relationship(  # type: ignore[name-defined]
        "Household", back_populates="collection_records"
    )
    collector: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", back_populates="collection_records", foreign_keys=[collected_by]
    )

    def __repr__(self) -> str:
        return f"<CollectionRecord id={self.id} household_id={self.household_id}>"


class VerificationRecord(UUIDMixin, TimestampMixin, Base):
    """
    Written when a Field User verifies a household they visited.
    """
    __tablename__ = "verification_records"

    household_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("households.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    verified_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verificationstatus"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    household: Mapped["Household"] = relationship(  # type: ignore[name-defined]
        "Household", back_populates="verification_records"
    )
    verifier: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", back_populates="verification_records", foreign_keys=[verified_by]
    )

    def __repr__(self) -> str:
        return f"<VerificationRecord id={self.id} status={self.status}>"
