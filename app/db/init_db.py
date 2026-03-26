import logging

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import engine, Base
from app.models import user      # noqa: F401 – register models
from app.models import household  # noqa: F401
from app.models import record    # noqa: F401
from app.models import building  # noqa: F401

logger = logging.getLogger(__name__)
settings = get_settings()


async def init_db() -> None:
    """Create all tables and seed SUPER_ADMIN if missing."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured.")

    await _seed_super_admin()


async def _seed_super_admin() -> None:
    from app.db.session import AsyncSessionLocal
    from app.models.user import User, UserRole
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.role == UserRole.SUPER_ADMIN)
        )
        if result.scalars().first():
            logger.info("Super Admin already exists – skipping seed.")
            return

        admin = User(
            name=settings.SUPER_ADMIN_NAME,
            phone=settings.SUPER_ADMIN_PHONE,
            password_hash=hash_password(settings.SUPER_ADMIN_PASSWORD),
            role=UserRole.SUPER_ADMIN,
        )
        session.add(admin)
        await session.commit()
        logger.info("Super Admin seeded: phone=%s", settings.SUPER_ADMIN_PHONE)