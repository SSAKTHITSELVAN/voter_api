import logging
import math
import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, literal_column, select
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
    HouseholdUpdate,
)
from app.services.file_storage import FileStorageService

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

    Uses literal_column() so that the result supports SQLAlchemy operators
    like <=, which TextClause does not.
    """
    expr = (
        f"{_EARTH_RADIUS_M} * 2 * ASIN("
        f"    SQRT("
        f"        POWER(SIN((RADIANS(households.latitude) - RADIANS({lat})) / 2), 2)"
        f"        + COS(RADIANS({lat})) * COS(RADIANS(households.latitude))"
        f"        * POWER(SIN((RADIANS(households.longitude) - RADIANS({lon})) / 2), 2)"
        f"    )"
        f")"
    )
    return literal_column(expr)


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
        self.storage = FileStorageService()

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
                distance_expr <= radius,  # now works: literal_column supports <=
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
        if not rows:
            return []

        household_ids = [household.id for household, _ in rows]
        image_rows = (
            await self.db.execute(
                select(
                    HouseholdImage.household_id,
                    HouseholdImage.image_url,
                    HouseholdImage.created_at,
                )
                .where(HouseholdImage.household_id.in_(household_ids))
                .order_by(HouseholdImage.household_id, HouseholdImage.created_at)
            )
        ).all()

        image_meta: dict[UUID, dict[str, str | int | None]] = {
            household_id: {
                "count": 0,
                "first_url": None,
            }
            for household_id in household_ids
        }

        for household_id, image_url, _created_at in image_rows:
            meta = image_meta.setdefault(
                household_id,
                {"count": 0, "first_url": None},
            )
            meta["count"] = int(meta["count"] or 0) + 1
            if meta["first_url"] is None:
                meta["first_url"] = image_url

        return [
            HouseholdBrief(
                id=household.id,
                latitude=household.latitude,
                longitude=household.longitude,
                address_text=household.address_text,
                house_type=household.house_type,
                created_at=household.created_at,
                distance_metres=round(dist, 2),
                landmark_image_count=int(image_meta.get(household.id, {}).get("count", 0) or 0),
                landmark_image_url=image_meta.get(household.id, {}).get("first_url"),
            )
            for household, dist in rows
        ]

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def list_households(self, limit: int = 50, offset: int = 0, search: str | None = None) -> tuple[list[Household], int]:
        from sqlalchemy import or_
        q = select(Household).where(Household.deleted_at.is_(None))
        if search:
            q = q.where(
                or_(
                    Household.address_text.ilike(f"%{search}%"),
                    Household.id.cast(str).ilike(f"%{search}%"),
                )
            )

        # Count total
        count_q = select(func.count()).select_from(q.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        # Get instances with persons/images preloaded
        q = q.options(
            selectinload(Household.persons),
            selectinload(Household.images)
        ).order_by(Household.created_at.desc()).offset(offset).limit(limit)

        items = (await self.db.execute(q)).scalars().all()
        return list(items), total

    async def create_household(
        self,
        payload: HouseholdCreate,
        creator: User,
        landmark_image_files: list[UploadFile] | None = None,
    ) -> Household:
        uploaded_files = list(landmark_image_files or [])
        uploaded_file_urls: list[str] = []
        upload_handled = False

        try:
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

            total_images = len(payload.landmark_image_urls) + len(uploaded_files)
            if total_images > settings.HOUSEHOLD_IMAGE_LIMIT:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Maximum {settings.HOUSEHOLD_IMAGE_LIMIT} landmark images "
                        "allowed per household."
                    ),
                )

            household = Household(
                id=uuid.uuid4(),
                latitude=payload.latitude,
                longitude=payload.longitude,
                address_text=payload.address_text,
                landmark_description=None,
                house_type=payload.house_type,
                unit_id=payload.unit_id,
                created_by=creator.id,
            )
            self.db.add(household)

            if uploaded_files:
                upload_handled = True
                uploaded_file_urls = await self.storage.save_household_images(
                    household.id,
                    uploaded_files,
                )

            for p in payload.persons:
                household.persons.append(
                    Person(
                        name=p.name,
                        age=p.age,
                        gender=p.gender,
                        is_voter=p.is_voter,
                    )
                )

            for url in [*payload.landmark_image_urls, *uploaded_file_urls]:
                household.images.append(
                    HouseholdImage(
                        image_url=url,
                        uploaded_by=creator.id,
                    )
                )

            await self.db.flush()
            await self.db.refresh(household)
            logger.info("Household created: id=%s by=%s", household.id, creator.id)
            return household
        except Exception:
            if uploaded_file_urls:
                self.storage.delete_urls(uploaded_file_urls)
            if uploaded_files and not upload_handled:
                await self.storage.close_files(uploaded_files)
            raise

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

    async def update_household(self, household_id: UUID, payload: HouseholdUpdate, requester: User) -> Household:
        """Partially update address, house_type, unit_id, and/or the full persons list."""
        household = await self.get_household_by_id(household_id)

        if payload.address_text is not None:
            household.address_text = payload.address_text
        if payload.house_type is not None:
            household.house_type = payload.house_type
        if payload.unit_id is not None or payload.house_type == "INDIVIDUAL":
            household.unit_id = payload.unit_id

        # Replace all persons if a new list is provided
        if payload.persons is not None:
            # Remove existing persons
            for person in list(household.persons):
                await self.db.delete(person)
            await self.db.flush()
            # Re-load after deletion
            household.persons.clear()
            # Insert new persons
            for p in payload.persons:
                household.persons.append(
                    Person(
                        name=p.name,
                        age=p.age,
                        gender=p.gender,
                        is_voter=p.is_voter,
                    )
                )

        await self.db.flush()
        await self.db.refresh(household)
        logger.info("Household updated: id=%s by=%s", household.id, requester.id)
        return household

    async def delete_person(self, household_id: UUID, person_id: UUID, requester: User) -> None:
        """Remove a single person from a household."""
        household = await self.get_household_by_id(household_id)
        person = next((p for p in household.persons if p.id == person_id), None)
        if not person:
            raise HTTPException(status_code=404, detail="Person not found in this household.")
        await self.db.delete(person)
        await self.db.flush()
        logger.info("Person removed: id=%s from household=%s by=%s", person_id, household_id, requester.id)

    async def add_image(
        self, household_id: UUID, image_url: str, uploader: User
    ) -> HouseholdImage:
        await self.get_household_by_id(household_id)

        count = await self._count_images(household_id)
        if count >= settings.HOUSEHOLD_IMAGE_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Maximum {settings.HOUSEHOLD_IMAGE_LIMIT} landmark images "
                    "already reached for this household."
                ),
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
        self,
        payload: BulkHouseholdCreate,
        creator: User,
        landmark_image_files_by_index: dict[int, list[UploadFile]] | None = None,
    ) -> BulkUploadResult:
        created = 0
        skipped = 0
        errors: list[dict] = []
        files_by_index = landmark_image_files_by_index or {}
        # ── within-batch dedup: track GPS coords already processed in this batch ──
        seen_coords: set[tuple[float, float]] = set()

        for idx, h_data in enumerate(payload.households):
            coord_key = (round(h_data.latitude, 6), round(h_data.longitude, 6))
            if coord_key in seen_coords:
                skipped += 1
                logger.info("Bulk upload: skipping index %d (duplicate within batch)", idx)
                continue

            try:
                await self.create_household(
                    h_data,
                    creator,
                    landmark_image_files=files_by_index.get(idx, []),
                )
                created += 1
                seen_coords.add(coord_key)

            except HTTPException as exc:
                if exc.status_code == status.HTTP_409_CONFLICT:
                    skipped += 1
                    seen_coords.add(coord_key)
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



