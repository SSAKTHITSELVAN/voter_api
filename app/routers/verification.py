from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.household import VerificationCreate, VerificationRead
from app.services.verification_service import VerificationService

router = APIRouter(prefix="/verification", tags=["Verification"])

_allowed = (UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.FIELD_USER)


@router.post(
    "",
    response_model=VerificationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a verification result for a household",
)
async def submit_verification(
    payload: VerificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_allowed)),
) -> VerificationRead:
    """
    Mark a household as **MATCHED** or **MISMATCH**.
    Field users typically call this after visiting a nearby household.
    Multiple verifications per household are stored (full audit trail).
    """
    record = await VerificationService(db).create_verification(payload, current_user)
    return VerificationRead.model_validate(record)
