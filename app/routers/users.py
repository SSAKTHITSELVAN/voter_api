from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse
from app.schemas.user import UserCreate, UserList, UserRead
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (SUPER_ADMIN creates ADMIN; ADMIN creates FIELD_USER)",
)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
) -> UserRead:
    user = await UserService(db).create_user(payload, current_user)
    return UserRead.model_validate(user)


@router.get(
    "",
    response_model=UserList,
    summary="List users visible to the caller",
)
async def list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
) -> UserList:
    users, total = await UserService(db).list_users(current_user, limit, offset)
    return UserList(items=[UserRead.model_validate(u) for u in users], total=total)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get the authenticated caller's profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserRead:
    return UserRead.model_validate(current_user)


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get a specific user by ID",
)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
) -> UserRead:
    from uuid import UUID
    user = await UserService(db).get_by_id(UUID(user_id))
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found.")
    return UserRead.model_validate(user)


@router.delete(
    "/{user_id}",
    response_model=MessageResponse,
    summary="Soft-delete a user",
)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
) -> MessageResponse:
    from uuid import UUID
    await UserService(db).soft_delete_user(UUID(user_id), current_user)
    return MessageResponse(message="User deactivated successfully.")
