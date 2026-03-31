import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.building import Building, Unit
from app.models.user import User
from app.schemas.building import BuildingCreate, UnitCreate, BuildingUpdate, UnitUpdate

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
            ).order_by(Unit.created_at.desc())
        )
        return list(result.scalars().all())

    # ── Edit / Delete ─────────────────────────────────────────────────────────

    async def list_buildings(self, limit: int = 50, offset: int = 0, search: str | None = None) -> tuple[list[Building], int]:
        q = select(Building).where(Building.deleted_at.is_(None))
        if search:
            q = q.where(
                or_(
                    Building.name.ilike(f"%{search}%"),
                    Building.address_text.ilike(f"%{search}%"),
                    Building.id.cast(str).ilike(f"%{search}%"),
                )
            )

        # Count total
        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        # Get instances
        q = q.order_by(Building.created_at.desc()).offset(offset).limit(limit)
        items = (await self.db.execute(q)).scalars().all()
        return list(items), total

    async def update_building(self, building_id: UUID, payload: BuildingUpdate, requester: User) -> Building:
        building = await self.get_building(building_id)
        if payload.name is not None:
            building.name = payload.name
        if payload.address_text is not None:
            building.address_text = payload.address_text
        if payload.total_floors is not None:
            building.total_floors = payload.total_floors

        await self.db.flush()
        await self.db.refresh(building)
        logger.info("Building updated: id=%s by=%s", building.id, requester.id)
        return building

    async def soft_delete_building(self, building_id: UUID, requester: User) -> None:
        building = await self.get_building(building_id)
        building.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
        logger.info("Building soft-deleted: id=%s by=%s", building.id, requester.id)

    async def update_unit(self, unit_id: UUID, payload: UnitUpdate, requester: User) -> Unit:
        unit = await self.get_unit(unit_id)
        if payload.flat_number is not None:
            unit.flat_number = payload.flat_number
        if payload.floor_number is not None:
            unit.floor_number = payload.floor_number

        await self.db.flush()
        await self.db.refresh(unit)
        logger.info("Unit updated: id=%s by=%s", unit.id, requester.id)
        return unit

    async def soft_delete_unit(self, unit_id: UUID, requester: User) -> None:
        unit = await self.get_unit(unit_id)
        unit.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
        logger.info("Unit soft-deleted: id=%s by=%s", unit.id, requester.id)

