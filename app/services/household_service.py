import logging
import math
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.household import Household, HouseholdImage, Person
from app.models.user import User
from app.schemas.household import (
    BulkHouseholdCreate,
    BulkUploadResult,
    HouseholdBrief,
    HouseholdCreate,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Earth radius in metres
_EARTH_RADIUS_M = 6_371_000.0


def _haversine_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Pure-Python Haversine – used only for in-memory fallback / tests."""
    r = _EARTH_RADIUS_M
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _haversine_sql(lat: float, lon: float):
    """
    Returns a SQLAlchemy column expression that computes the Haversine distance
    (in metres) between (lat, lon) and the household's stored lat/lng columns.
    Works on plain PostgreSQL with no extensions.
    """
    return text(
        """
        :earth_r * 2 * ASIN(
            SQRT(
                POWER(SIN((RADIANS(households.latitude) - RADIANS(:lat)) / 2), 2)
                + COS(RADIANS(:lat)) * COS(RADIANS(households.latitude))
                * POWER(SIN((RADIANS(households.longitude) - RADIANS(:lon)) / 2), 2)
            )
        )
        """
    ).bindparams(earth_r=_EARTH_RADIUS_M, lat=lat, lon=lon)


def _bbox_filter(lat: float, lon: float, radius_m: float):
    """
    A cheap bounding-box pre-filter to let Postgres use a plain index before
    evaluating the more expensive Haversine expression.
    1 degree latitude ≈ 111 320 m; longitude degree shrinks with cos(lat).
    """
    deg_lat = radius_m / 111_320.0
    deg_lon = radius_m / (111_320.0 * math.cos(math.radians(lat)) + 1e-9)
    return (
        Household.latitude.between(lat - deg_lat, lat + deg_lat),
        Household.longitude.between(lon - deg_lon, lon + deg_lon),
    )


class HouseholdService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _count_images(self, household_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(HouseholdImage)
            .where(HouseholdImage.household_id == household_id)
        )
        return result.scalar_one()

    # ── Duplicate Detection ───────────────────────────────────────────────────

    async def find_nearby_duplicates(
        self,
        lat: float,
        lon: float,
        radius_metres: int | None = None,
        exclude_id: UUID | None = None,
    ) -> list[Household]:
        """Return households within radius_metres of (lat, lon)."""
        radius = radius_metres or settings.DUPLICATE_RADIUS_METRES
        bbox = _bbox_filter(lat, lon, radius)
        distance_expr = _haversine_sql(lat, lon)

        q = (
            select(Household)
            .where(
                Household.deleted_at.is_(None),
                *bbox,
                distance_expr <= radius,
            )
        )
        if exclude_id:
            q = q.where(Household.id != exclude_id)

        result = await self.db.execute(q)
        return list(result.scalars().all())

    # ── Geo Search ────────────────────────────────────────────────────────────

    async def get_nearby(
        self,
        lat: float,
        lon: float,
        radius_metres: float,
        limit: int = 50,
    ) -> list[HouseholdBrief]:
        """
        Return nearby households ordered by distance, with distance_metres attached.
        """
        bbox = _bbox_filter(lat, lon, radius_metres)
        distance_expr = _haversine_sql(lat, lon).label("distance_metres")

        q = (
            select(Household, distance_expr)
            .where(
                Household.deleted_at.is_(None),
                *bbox,
                _haversine_sql(lat, lon) <= radius_metres,
            )
            .order_by(distance_expr)
            .limit(limit)
        )

        rows = (await self.db.execute(q)).all()
        return [
            HouseholdBrief(
                id=household.id,
                latitude=household.latitude,
                longitude=household.longitude,
                address_text=household.address_text,
                house_type=household.house_type,
                created_at=household.created_at,
                distance_metres=round(dist, 2),
            )
            for household, dist in rows
        ]

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def create_household(
        self, payload: HouseholdCreate, creator: User
    ) -> Household:
        # 1. Duplicate check
        dupes = await self.find_nearby_duplicates(payload.latitude, payload.longitude)
        if dupes:
            ids = [str(d.id) for d in dupes]
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Possible duplicate household(s) found within 20 metres.",
                    "duplicate_ids": ids,
                },
            )

        # 2. Create household
        household = Household(
            latitude=payload.latitude,
            longitude=payload.longitude,
            address_text=payload.address_text,
            landmark_description=payload.landmark_description,
            house_type=payload.house_type,
            unit_id=payload.unit_id,
            created_by=creator.id,
        )
        self.db.add(household)
        await self.db.flush()  # get household.id

        # 3. Persons
        for p in payload.persons:
            person = Person(
                household_id=household.id,
                age=p.age,
                gender=p.gender,
                is_voter=p.is_voter,
            )
            self.db.add(person)

        # 4. Images (max 5)
        if len(payload.image_urls) > 5:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Maximum 5 images allowed per household.",
            )
        for url in payload.image_urls:
            img = HouseholdImage(
                household_id=household.id,
                image_url=url,
                uploaded_by=creator.id,
            )
            self.db.add(img)

        await self.db.flush()
        await self.db.refresh(household)
        logger.info("Household created: id=%s by=%s", household.id, creator.id)
        return household

    async def get_household_by_id(self, household_id: UUID) -> Household:
        result = await self.db.execute(
            select(Household)
            .options(
                selectinload(Household.persons),
                selectinload(Household.images),
            )
            .where(
                Household.id == household_id,
                Household.deleted_at.is_(None),
            )
        )
        household = result.scalars().first()
        if not household:
            raise HTTPException(status_code=404, detail="Household not found.")
        return household

    async def soft_delete_household(self, household_id: UUID, requester: User) -> None:
        household = await self.get_household_by_id(household_id)
        household.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def add_image(
        self, household_id: UUID, image_url: str, uploader: User
    ) -> HouseholdImage:
        await self.get_household_by_id(household_id)

        count = await self._count_images(household_id)
        if count >= 5:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Maximum 5 images already reached for this household.",
            )

        img = HouseholdImage(
            household_id=household_id,
            image_url=image_url,
            uploaded_by=uploader.id,
        )
        self.db.add(img)
        await self.db.flush()
        await self.db.refresh(img)
        return img

    # ── Bulk Upload (Offline Sync) ────────────────────────────────────────────

    async def bulk_create_households(
        self, payload: BulkHouseholdCreate, creator: User
    ) -> BulkUploadResult:
        created = 0
        skipped = 0
        errors: list[dict] = []

        for idx, h_data in enumerate(payload.households):
            try:
                dupes = await self.find_nearby_duplicates(
                    h_data.latitude, h_data.longitude
                )
                if dupes:
                    skipped += 1
                    continue

                await self.create_household(h_data, creator)
                created += 1

            except HTTPException as exc:
                if exc.status_code == status.HTTP_409_CONFLICT:
                    skipped += 1
                else:
                    errors.append({"index": idx, "detail": str(exc.detail)})
            except Exception as exc:
                logger.exception("Bulk upload error at index %d", idx)
                errors.append({"index": idx, "detail": str(exc)})

        return BulkUploadResult(
            total=len(payload.households),
            created=created,
            duplicates_skipped=skipped,
            errors=errors,
        )