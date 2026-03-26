from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse
from app.schemas.household import (
    BulkHouseholdCreate,
    BulkUploadResult,
    DuplicateCheckResult,
    HouseholdBrief,
    HouseholdCreate,
    HouseholdRead,
    VerificationCreate,
    VerificationRead,
    CollectionRecordRead,
)
from app.services.household_service import HouseholdService
from app.services.verification_service import VerificationService

router = APIRouter(prefix="/households", tags=["Households"])

_field_roles = (UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.FIELD_USER)


# ── Create ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=HouseholdRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new household (with duplicate check)",
)
async def create_household(
    payload: HouseholdCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_field_roles)),
) -> HouseholdRead:
    """
    - Runs a **20-metre duplicate check** before inserting.
    - Returns `409 Conflict` with duplicate IDs if a match is found.
    - Pass `persons` list and `image_urls` (max 5) in the body.
    - For `APARTMENT` house_type, `unit_id` is **required**.
    """
    svc = HouseholdService(db)
    household = await svc.create_household(payload, current_user)
    await VerificationService(db).create_collection_record(
        household.id, current_user, raw_data=payload.model_dump()
    )
    full = await svc.get_household_by_id(household.id)
    return HouseholdRead.model_validate(full)


# ── Bulk Upload (Offline Sync) ────────────────────────────────────────────────

@router.post(
    "/bulk",
    response_model=BulkUploadResult,
    status_code=status.HTTP_200_OK,
    summary="Bulk upload households (offline sync)",
)
async def bulk_create_households(
    payload: BulkHouseholdCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_field_roles)),
) -> BulkUploadResult:
    """
    Submit up to **500 households** in a single request.
    Each household goes through the same duplicate-check logic.
    Duplicates are skipped (not errored).
    """
    return await HouseholdService(db).bulk_create_households(payload, current_user)


# ── Duplicate Check ───────────────────────────────────────────────────────────

@router.get(
    "/duplicate-check",
    response_model=DuplicateCheckResult,
    summary="Check for duplicate households near a GPS coordinate",
)
async def duplicate_check(
    latitude: float = Query(..., ge=-90.0, le=90.0),
    longitude: float = Query(..., ge=-180.0, le=180.0),
    radius_metres: int = Query(20, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_field_roles)),
) -> DuplicateCheckResult:
    dupes = await HouseholdService(db).find_nearby_duplicates(
        latitude, longitude, radius_metres
    )
    return DuplicateCheckResult(
        has_duplicates=bool(dupes),
        duplicates=[HouseholdBrief.model_validate(h) for h in dupes],
    )


# ── Nearby Search ─────────────────────────────────────────────────────────────

@router.get(
    "/nearby",
    response_model=list[HouseholdBrief],
    summary="Get households within a radius (Haversine)",
)
async def get_nearby_households(
    latitude: float = Query(..., ge=-90.0, le=90.0),
    longitude: float = Query(..., ge=-180.0, le=180.0),
    radius_metres: float = Query(500.0, ge=1.0, le=50000.0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_field_roles)),
) -> list[HouseholdBrief]:
    """
    Uses **Haversine formula** for geo search on plain PostgreSQL.
    Results include `distance_metres` and are ordered nearest-first.
    """
    return await HouseholdService(db).get_nearby(latitude, longitude, radius_metres, limit)


# ── Get Single ────────────────────────────────────────────────────────────────

@router.get(
    "/{household_id}",
    response_model=HouseholdRead,
    summary="Get full household details",
)
async def get_household(
    household_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_field_roles)),
) -> HouseholdRead:
    household = await HouseholdService(db).get_household_by_id(household_id)
    return HouseholdRead.model_validate(household)


# ── Soft Delete ───────────────────────────────────────────────────────────────

@router.delete(
    "/{household_id}",
    response_model=MessageResponse,
    summary="Soft-delete a household",
)
async def delete_household(
    household_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SUPER_ADMIN, UserRole.ADMIN)
    ),
) -> MessageResponse:
    await HouseholdService(db).soft_delete_household(household_id, current_user)
    return MessageResponse(message="Household soft-deleted.")


# ── Collection Records ────────────────────────────────────────────────────────

@router.get(
    "/{household_id}/collection-records",
    response_model=list[CollectionRecordRead],
    summary="Audit trail: collection records for a household",
)
async def list_collection_records(
    household_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_field_roles)),
) -> list[CollectionRecordRead]:
    records = await VerificationService(db).list_collection_records_for_household(
        household_id
    )
    return [CollectionRecordRead.model_validate(r) for r in records]


# ── Verification History ──────────────────────────────────────────────────────

@router.get(
    "/{household_id}/verifications",
    response_model=list[VerificationRead],
    summary="Audit trail: verification history for a household",
)
async def list_verifications(
    household_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_field_roles)),
) -> list[VerificationRead]:
    records = await VerificationService(db).list_verifications_for_household(household_id)
    return [VerificationRead.model_validate(r) for r in records]