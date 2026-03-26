import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate

logger = logging.getLogger(__name__)

# Which roles are allowed to create which roles
CREATION_POLICY: dict[UserRole, list[UserRole]] = {
    UserRole.SUPER_ADMIN: [UserRole.ADMIN],
    UserRole.ADMIN: [UserRole.FIELD_USER],
    UserRole.FIELD_USER: [],
}


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Reads ─────────────────────────────────────────────────────────────────

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        return result.scalars().first()

    async def get_by_phone(self, phone: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.phone == phone, User.deleted_at.is_(None))
        )
        return result.scalars().first()

    async def list_users(
        self,
        requester: User,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[User], int]:
        """
        SUPER_ADMIN sees all users.
        ADMIN sees only users they created.
        FIELD_USER cannot list users (enforced at router level).
        """
        base_q = select(User).where(User.deleted_at.is_(None))
        count_q = select(func.count()).select_from(User).where(User.deleted_at.is_(None))

        if requester.role == UserRole.ADMIN:
            base_q = base_q.where(User.created_by == requester.id)
            count_q = count_q.where(User.created_by == requester.id)

        total = (await self.db.execute(count_q)).scalar_one()
        users = (
            await self.db.execute(base_q.offset(offset).limit(limit))
        ).scalars().all()

        return list(users), total

    # ── Writes ────────────────────────────────────────────────────────────────

    async def create_user(self, payload: UserCreate, creator: User) -> User:
        # Enforce creation policy
        allowed = CREATION_POLICY.get(creator.role, [])
        if payload.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"A {creator.role} cannot create a {payload.role} user. "
                    f"Allowed: {[r.value for r in allowed]}"
                ),
            )

        # Uniqueness check
        existing = await self.get_by_phone(payload.phone)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Phone number {payload.phone} is already registered.",
            )

        user = User(
            name=payload.name,
            phone=payload.phone,
            password_hash=hash_password(payload.password),
            role=payload.role,
            created_by=creator.id,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        logger.info("User created: id=%s role=%s by=%s", user.id, user.role, creator.id)
        return user

    async def soft_delete_user(self, user_id: UUID, requester: User) -> User:
        user = await self.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")

        # Only creator or SUPER_ADMIN can delete
        if requester.role != UserRole.SUPER_ADMIN and user.created_by != requester.id:
            raise HTTPException(status_code=403, detail="Not authorised to delete this user.")

        user.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
        return user
