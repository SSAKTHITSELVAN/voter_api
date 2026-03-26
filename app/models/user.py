import uuid
import enum

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDMixin, TimestampMixin, SoftDeleteMixin


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    FIELD_USER = "FIELD_USER"


class User(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="userrole"), nullable=False)

    # Self-referential: who created this user
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    creator: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by], remote_side="User.id"
    )
    created_users: Mapped[list["User"]] = relationship(
        "User", foreign_keys=[created_by], back_populates="creator"
    )
    households: Mapped[list["Household"]] = relationship(  # type: ignore[name-defined]
        "Household", back_populates="creator", foreign_keys="Household.created_by"
    )
    collection_records: Mapped[list["CollectionRecord"]] = relationship(  # type: ignore
        "CollectionRecord", back_populates="collector"
    )
    verification_records: Mapped[list["VerificationRecord"]] = relationship(  # type: ignore
        "VerificationRecord", back_populates="verifier"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} phone={self.phone} role={self.role}>"
