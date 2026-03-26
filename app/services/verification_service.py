import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.record import CollectionRecord, VerificationRecord
from app.models.household import Household, Person
from app.models.user import User
from app.schemas.household import VerificationCreate

logger = logging.getLogger(__name__)


class VerificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_verification(
        self, payload: VerificationCreate, verifier: User
    ) -> VerificationRecord:
        # Ensure household exists
        result = await self.db.execute(
            select(Household).where(
                Household.id == payload.household_id,
                Household.deleted_at.is_(None),
            )
        )
        household = result.scalars().first()
        if household is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Household not found.")

        record = VerificationRecord(
            household_id=payload.household_id,
            verified_by=verifier.id,
            status=payload.status,
            notes=payload.notes,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        logger.info(
            "Verification created: id=%s household=%s status=%s by=%s",
            record.id, payload.household_id, payload.status, verifier.id,
        )
        return record

    async def create_collection_record(
        self,
        household_id: UUID,
        collector: User,
        raw_data: dict | None = None,
    ) -> CollectionRecord:
        """
        Auto-compute total_people and total_voters from Person rows.
        Stores a raw_data snapshot (useful for offline sync payloads).
        """
        persons_result = await self.db.execute(
            select(Person).where(Person.household_id == household_id)
        )
        persons = persons_result.scalars().all()

        total_people = len(persons)
        total_voters = sum(1 for p in persons if p.is_voter)

        rec = CollectionRecord(
            household_id=household_id,
            collected_by=collector.id,
            total_people=total_people,
            total_voters=total_voters,
            raw_data_json=raw_data,
        )
        self.db.add(rec)
        await self.db.flush()
        await self.db.refresh(rec)
        logger.info(
            "CollectionRecord created: id=%s household=%s people=%d voters=%d",
            rec.id, household_id, total_people, total_voters,
        )
        return rec

    async def list_verifications_for_household(
        self, household_id: UUID
    ) -> list[VerificationRecord]:
        result = await self.db.execute(
            select(VerificationRecord)
            .where(VerificationRecord.household_id == household_id)
            .order_by(VerificationRecord.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_collection_records_for_household(
        self, household_id: UUID
    ) -> list[CollectionRecord]:
        result = await self.db.execute(
            select(CollectionRecord)
            .where(CollectionRecord.household_id == household_id)
            .order_by(CollectionRecord.created_at.desc())
        )
        return list(result.scalars().all())
