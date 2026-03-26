import logging

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def login(self, payload: LoginRequest) -> TokenResponse:
        svc = UserService(self.db)
        user = await svc.get_by_phone(payload.phone)

        if user is None or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid phone number or password.",
            )

        if user.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account has been deactivated.",
            )

        token = create_access_token(subject=str(user.id), role=user.role.value)
        logger.info("Login successful: user_id=%s role=%s", user.id, user.role)

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            role=user.role.value,
            user_id=str(user.id),
        )
