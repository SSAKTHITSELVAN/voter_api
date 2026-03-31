from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.building import BuildingCreate, BuildingRead, UnitCreate, UnitRead, BuildingUpdate, UnitUpdate
from app.schemas.common import MessageResponse
from app.services.building_service import BuildingService

router = APIRouter(prefix="/buildings", tags=["Buildings & Units"])

_admin_roles = (UserRole.SUPER_ADMIN, UserRole.ADMIN)


@router.post(
    "",
    response_model=BuildingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new apartment building",
)
async def create_building(
    payload: BuildingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_admin_roles)),
) -> BuildingRead:
    building = await BuildingService(db).create_building(payload, current_user)
    return BuildingRead.model_validate(building)


@router.get(
    "/all",
    summary="Admin: List all buildings with pagination and search",
)
async def list_buildings(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_admin_roles)),
) -> dict:
    svc = BuildingService(db)
    items, total = await svc.list_buildings(limit, offset, search)
    return {
        "items": [BuildingRead.model_validate(b) for b in items],
        "total": total,
    }


@router.get("/{building_id}", response_model=BuildingRead, summary="Get building details")
async def get_building(
    building_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BuildingRead:
    building = await BuildingService(db).get_building(building_id)
    return BuildingRead.model_validate(building)


@router.put(
    "/{building_id}",
    response_model=BuildingRead,
    summary="Update a building (Admin)",
)
async def update_building(
    building_id: UUID,
    payload: BuildingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_admin_roles)),
) -> BuildingRead:
    building = await BuildingService(db).update_building(building_id, payload, current_user)
    return BuildingRead.model_validate(building)


@router.delete(
    "/{building_id}",
    response_model=MessageResponse,
    summary="Soft-delete a building (Admin)",
)
async def delete_building(
    building_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_admin_roles)),
) -> MessageResponse:
    await BuildingService(db).soft_delete_building(building_id, current_user)
    return MessageResponse(message="Building soft-deleted.")


# ── Units ────────────────────────────────────────────────────────────────────

@router.post(
    "/units",
    response_model=UnitRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a unit/flat to a building",
)
async def create_unit(
    payload: UnitCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_admin_roles)),
) -> UnitRead:
    unit = await BuildingService(db).create_unit(payload, current_user)
    return UnitRead.model_validate(unit)


@router.get(
    "/{building_id}/units",
    response_model=list[UnitRead],
    summary="List all units in a building",
)
async def list_units(
    building_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UnitRead]:
    units = await BuildingService(db).list_units_for_building(building_id)
    return [UnitRead.model_validate(u) for u in units]


@router.put(
    "/units/{unit_id}",
    response_model=UnitRead,
    summary="Update a unit (Admin)",
)
async def update_unit(
    unit_id: UUID,
    payload: UnitUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_admin_roles)),
) -> UnitRead:
    unit = await BuildingService(db).update_unit(unit_id, payload, current_user)
    return UnitRead.model_validate(unit)


@router.delete(
    "/units/{unit_id}",
    response_model=MessageResponse,
    summary="Soft-delete a unit (Admin)",
)
async def delete_unit(
    unit_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_admin_roles)),
) -> MessageResponse:
    await BuildingService(db).soft_delete_unit(unit_id, current_user)
    return MessageResponse(message="Unit soft-deleted.")
