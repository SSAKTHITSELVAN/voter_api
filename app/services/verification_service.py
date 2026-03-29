import csv
import json
import logging
from io import StringIO
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.household import Household, Person
from app.models.record import CollectionRecord, VerificationRecord
from app.models.user import User
from app.schemas.household import VerificationCreate

logger = logging.getLogger(__name__)


class VerificationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_verification(
        self, payload: VerificationCreate, verifier: User
    ) -> VerificationRecord:
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
            record.id,
            payload.household_id,
            payload.status,
            verifier.id,
        )
        return record

    async def create_collection_record(
        self,
        household_id: UUID,
        collector: User,
        raw_data: dict | None = None,
    ) -> CollectionRecord:
        persons_result = await self.db.execute(
            select(Person).where(Person.household_id == household_id)
        )
        persons = persons_result.scalars().all()

        total_people = len(persons)
        total_voters = sum(1 for person in persons if person.is_voter)

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
            rec.id,
            household_id,
            total_people,
            total_voters,
        )
        return rec

    def _serialize_collection_record(
        self,
        record: CollectionRecord,
        collector: User | None,
        household: Household | None,
    ) -> dict:
        return {
            "id": record.id,
            "household_id": record.household_id,
            "collected_by": record.collected_by,
            "collected_by_name": collector.name if collector else None,
            "collected_by_phone": collector.phone if collector else None,
            "collected_by_role": collector.role if collector else None,
            "household_address_text": household.address_text if household else None,
            "household_house_type": household.house_type if household else None,
            "household_latitude": household.latitude if household else None,
            "household_longitude": household.longitude if household else None,
            "total_people": record.total_people,
            "total_voters": record.total_voters,
            "raw_data_json": record.raw_data_json,
            "created_at": record.created_at,
        }

    def _extract_person_rows(self, record: dict) -> list[dict[str, Any]]:
        raw_data = record.get("raw_data_json")
        if not isinstance(raw_data, dict):
            return []
        persons = raw_data.get("persons")
        if not isinstance(persons, list):
            return []
        return [person for person in persons if isinstance(person, dict)]

    def _build_person_summary(self, record: dict) -> str:
        summary_parts: list[str] = []
        for person in self._extract_person_rows(record):
            raw_name = person.get("name")
            name = str(raw_name).strip() if raw_name not in (None, "") else ""
            age = person.get("age")
            if name and age not in (None, ""):
                summary_parts.append(f"{name} (Age {age})")
            elif name:
                summary_parts.append(name)
            elif age not in (None, ""):
                summary_parts.append(f"Age {age}")
        return "; ".join(summary_parts)

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
    ) -> list[dict]:
        result = await self.db.execute(
            select(CollectionRecord, User, Household)
            .outerjoin(User, CollectionRecord.collected_by == User.id)
            .outerjoin(Household, CollectionRecord.household_id == Household.id)
            .where(CollectionRecord.household_id == household_id)
            .order_by(CollectionRecord.created_at.desc())
        )
        return [
            self._serialize_collection_record(record, collector, household)
            for record, collector, household in result.all()
        ]

    async def list_collection_records(
        self,
        *,
        limit: int = 200,
        offset: int = 0,
        search: str | None = None,
        collector_id: UUID | None = None,
        household_id: UUID | None = None,
        record_id: UUID | None = None,
    ) -> list[dict]:
        query = (
            select(CollectionRecord, User, Household)
            .outerjoin(User, CollectionRecord.collected_by == User.id)
            .outerjoin(Household, CollectionRecord.household_id == Household.id)
            .order_by(CollectionRecord.created_at.desc())
        )

        if collector_id is not None:
            query = query.where(CollectionRecord.collected_by == collector_id)
        if household_id is not None:
            query = query.where(CollectionRecord.household_id == household_id)
        if record_id is not None:
            query = query.where(CollectionRecord.id == record_id)
        if search:
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    User.name.ilike(term),
                    User.phone.ilike(term),
                    Household.address_text.ilike(term),
                )
            )

        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return [
            self._serialize_collection_record(record, collector, household)
            for record, collector, household in result.all()
        ]

    def export_collection_records_csv(self, records: list[dict]) -> str:
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "record_id",
                "household_id",
                "collector_id",
                "collector_name",
                "collector_phone",
                "collector_role",
                "household_address_text",
                "household_house_type",
                "household_latitude",
                "household_longitude",
                "total_people",
                "total_voters",
                "persons_summary",
                "persons_json",
                "created_at",
                "raw_data_json",
            ],
        )
        writer.writeheader()

        for record in records:
            persons = self._extract_person_rows(record)
            writer.writerow(
                {
                    "record_id": record["id"],
                    "household_id": record["household_id"],
                    "collector_id": record["collected_by"],
                    "collector_name": record.get("collected_by_name") or "",
                    "collector_phone": record.get("collected_by_phone") or "",
                    "collector_role": record.get("collected_by_role") or "",
                    "household_address_text": record.get("household_address_text") or "",
                    "household_house_type": record.get("household_house_type") or "",
                    "household_latitude": record.get("household_latitude") or "",
                    "household_longitude": record.get("household_longitude") or "",
                    "total_people": record["total_people"],
                    "total_voters": record["total_voters"],
                    "persons_summary": self._build_person_summary(record),
                    "persons_json": json.dumps(persons, separators=(",", ":")),
                    "created_at": record["created_at"].isoformat()
                    if record.get("created_at")
                    else "",
                    "raw_data_json": json.dumps(
                        record.get("raw_data_json") or {},
                        separators=(",", ":"),
                    ),
                }
            )

        return output.getvalue()
