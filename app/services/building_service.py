import logging
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.building import Building, Unit
from app.models.user import User
from app.schemas.building import BuildingCreate, UnitCreate

logger = logging.getLogger(__name__)


class BuildingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_building(self, payload: BuildingCreate, creator: User) -> Building:
        building = Building(
            name=payload.name,
            address_text=payload.address_text,
            total_floors=payload.total_floors,
            created_by=creator.id,
        )
        self.db.add(building)
        await self.db.flush()
        await self.db.refresh(building)
        logger.info("Building created: id=%s by=%s", building.id, creator.id)
        return building

    async def get_building(self, building_id: UUID) -> Building:
        result = await self.db.execute(
            select(Building).where(
                Building.id == building_id,
                Building.deleted_at.is_(None),
            )
        )
        building = result.scalars().first()
        if not building:
            raise HTTPException(status_code=404, detail="Building not found.")
        return building

    async def create_unit(self, payload: UnitCreate, creator: User) -> Unit:
        # Ensure building exists
        await self.get_building(payload.building_id)

        unit = Unit(
            building_id=payload.building_id,
            flat_number=payload.flat_number,
            floor_number=payload.floor_number,
        )
        self.db.add(unit)
        await self.db.flush()
        await self.db.refresh(unit)
        logger.info("Unit created: id=%s building=%s", unit.id, payload.building_id)
        return unit

    async def get_unit(self, unit_id: UUID) -> Unit:
        result = await self.db.execute(
            select(Unit).where(
                Unit.id == unit_id,
                Unit.deleted_at.is_(None),
            )
        )
        unit = result.scalars().first()
        if not unit:
            raise HTTPException(status_code=404, detail="Unit not found.")
        return unit

    async def list_units_for_building(self, building_id: UUID) -> list[Unit]:
        result = await self.db.execute(
            select(Unit).where(
                Unit.building_id == building_id,
                Unit.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())
