import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDMixin, TimestampMixin, SoftDeleteMixin


class Building(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """
    Represents an apartment building.
    Multiple Unit rows belong to one Building.
    """
    __tablename__ = "buildings"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_floors: Mapped[int | None] = mapped_column(nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    units: Mapped[list["Unit"]] = relationship("Unit", back_populates="building")

    def __repr__(self) -> str:
        return f"<Building id={self.id} name={self.name}>"


class Unit(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """
    A flat / unit inside a Building.
    A Household of type APARTMENT links to a Unit.
    """
    __tablename__ = "units"

    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buildings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    flat_number: Mapped[str] = mapped_column(String(30), nullable=False)
    floor_number: Mapped[int | None] = mapped_column(nullable=True)

    building: Mapped["Building"] = relationship("Building", back_populates="units")
    household: Mapped["Household | None"] = relationship(  # type: ignore[name-defined]
        "Household", back_populates="unit", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Unit id={self.id} flat={self.flat_number}>"
