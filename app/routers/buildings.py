from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.building import BuildingCreate, BuildingRead, UnitCreate, UnitRead
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


@router.get("/{building_id}", response_model=BuildingRead, summary="Get building details")
async def get_building(
    building_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BuildingRead:
    from uuid import UUID
    building = await BuildingService(db).get_building(UUID(building_id))
    return BuildingRead.model_validate(building)


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
    building_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UnitRead]:
    from uuid import UUID
    units = await BuildingService(db).list_units_for_building(UUID(building_id))
    return [UnitRead.model_validate(u) for u in units]
