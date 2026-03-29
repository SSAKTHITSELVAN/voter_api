import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.core.dependencies import require_roles
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
_admin_roles = (UserRole.SUPER_ADMIN, UserRole.ADMIN)
_bulk_landmark_images_pattern = re.compile(r"^landmark_images(?:_|\[)(\d+)(?:\])?$")


@dataclass
class HouseholdCreateRequest:
    payload: HouseholdCreate
    landmark_images: list[UploadFile]


@dataclass
class BulkHouseholdCreateRequest:
    payload: BulkHouseholdCreate
    landmark_images_by_index: dict[int, list[UploadFile]]


async def _close_uploads(uploads: list[UploadFile]) -> None:
    for upload in uploads:
        await upload.close()

def _is_upload(value: Any) -> bool:
    return isinstance(value, (UploadFile, StarletteUploadFile))


def _parse_payload_model(payload_model: type[HouseholdCreate], raw_payload: Any) -> HouseholdCreate:
    try:
        return payload_model.model_validate(raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc


def _parse_bulk_payload_model(
    payload_model: type[BulkHouseholdCreate],
    raw_payload: Any,
) -> BulkHouseholdCreate:
    try:
        return payload_model.model_validate(raw_payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc


def _parse_json_text(raw_value: Any, field_name: str) -> Any:
    if raw_value is None or raw_value == "":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{field_name}' is required.",
        )

    try:
        return json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{field_name}' must contain valid JSON.",
        ) from exc


async def _parse_household_create_request(request: Request) -> HouseholdCreateRequest:
    content_type = request.headers.get("content-type", "").lower()

    if content_type.startswith("application/json"):
        try:
            raw_payload = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request body must contain valid JSON.",
            ) from exc
        return HouseholdCreateRequest(
            payload=_parse_payload_model(HouseholdCreate, raw_payload),
            landmark_images=[],
        )

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        all_uploads = [
            item for _, item in form.multi_items()
            if _is_upload(item)
        ]
        try:
            payload = _parse_payload_model(
                HouseholdCreate,
                _parse_json_text(form.get("payload"), "payload"),
            )
        except HTTPException:
            await _close_uploads(all_uploads)
            raise

        unknown_file_fields = [
            key for key, value in form.multi_items()
            if _is_upload(value) and key != "landmark_images"
        ]
        if unknown_file_fields:
            await _close_uploads(all_uploads)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Unexpected file field(s): "
                    + ", ".join(sorted(set(unknown_file_fields)))
                ),
            )

        landmark_images = [
            item for item in form.getlist("landmark_images")
            if _is_upload(item)
        ]
        return HouseholdCreateRequest(payload=payload, landmark_images=landmark_images)

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Use application/json or multipart/form-data for this endpoint.",
    )


async def _parse_bulk_household_create_request(
    request: Request,
) -> BulkHouseholdCreateRequest:
    content_type = request.headers.get("content-type", "").lower()

    if content_type.startswith("application/json"):
        try:
            raw_payload = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request body must contain valid JSON.",
            ) from exc
        return BulkHouseholdCreateRequest(
            payload=_parse_bulk_payload_model(BulkHouseholdCreate, raw_payload),
            landmark_images_by_index={},
        )

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        all_uploads: list[UploadFile] = []
        for key, value in form.multi_items():
            if not _is_upload(value):
                continue
            all_uploads.append(value)

        try:
            payload = _parse_bulk_payload_model(
                BulkHouseholdCreate,
                _parse_json_text(form.get("payload"), "payload"),
            )
        except HTTPException:
            await _close_uploads(all_uploads)
            raise

        landmark_images_by_index: dict[int, list[UploadFile]] = {}
        unknown_file_fields: list[str] = []
        out_of_range_indexes: list[int] = []

        for key, value in form.multi_items():
            if not _is_upload(value):
                continue

            match = _bulk_landmark_images_pattern.match(key)
            if not match:
                unknown_file_fields.append(key)
                continue

            index = int(match.group(1))
            if index >= len(payload.households):
                out_of_range_indexes.append(index)
                continue

            landmark_images_by_index.setdefault(index, []).append(value)

        if unknown_file_fields:
            await _close_uploads(all_uploads)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Unexpected file field(s) for bulk upload: "
                    + ", ".join(sorted(set(unknown_file_fields)))
                ),
            )

        if out_of_range_indexes:
            await _close_uploads(all_uploads)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "landmark_images_<index> fields must map to an existing household "
                    "index in payload."
                ),
            )

        return BulkHouseholdCreateRequest(
            payload=payload,
            landmark_images_by_index=landmark_images_by_index,
        )

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Use application/json or multipart/form-data for this endpoint.",
    )


_single_household_openapi = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": HouseholdCreate.model_json_schema(),
            },
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["payload"],
                    "properties": {
                        "payload": {
                            "type": "string",
                            "description": (
                                "JSON string matching the HouseholdCreate schema. "
                                "Use this together with repeated landmark_images files."
                            ),
                        },
                        "landmark_images": {
                            "type": "array",
                            "items": {"type": "string", "format": "binary"},
                            "maxItems": 5,
                            "description": "Up to 5 landmark image files.",
                        },
                    },
                }
            },
        },
    }
}


_bulk_household_openapi = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": BulkHouseholdCreate.model_json_schema(),
            },
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["payload"],
                    "properties": {
                        "payload": {
                            "type": "string",
                            "description": (
                                "JSON string matching the BulkHouseholdCreate schema."
                            ),
                        },
                        "landmark_images_0": {
                            "type": "array",
                            "items": {"type": "string", "format": "binary"},
                            "maxItems": 5,
                            "description": (
                                "Files for household index 0. Repeat the same pattern for "
                                "landmark_images_1, landmark_images_2, and so on."
                            ),
                        },
                    },
                }
            },
        },
    }
}


# ── Create ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=HouseholdRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new household (with duplicate check)",
    openapi_extra=_single_household_openapi,
)
async def create_household(
    household_request: HouseholdCreateRequest = Depends(_parse_household_create_request),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_field_roles)),
) -> HouseholdRead:
    """
    - Runs a **20-metre duplicate check** before inserting.
    - Returns `409 Conflict` with duplicate IDs if a match is found.
    - Preferred request: `multipart/form-data` with a `payload` JSON string plus
      repeated `landmark_images` files (max 5).
    - JSON clients can still send `landmark_image_urls` in the body.
    - For `APARTMENT` house_type, `unit_id` is **required**.
    """
    svc = HouseholdService(db)
    household = await svc.create_household(
        household_request.payload,
        current_user,
        landmark_image_files=household_request.landmark_images,
    )
    full = await svc.get_household_by_id(household.id)
    await VerificationService(db).create_collection_record(
        household.id,
        current_user,
        raw_data={
            **household_request.payload.model_dump(),
            "landmark_image_urls": [
                image.image_url for image in full.landmark_images
            ],
        },
    )
    return HouseholdRead.model_validate(full)


# ── Bulk Upload (Offline Sync) ────────────────────────────────────────────────

@router.post(
    "/bulk",
    response_model=BulkUploadResult,
    status_code=status.HTTP_200_OK,
    summary="Bulk upload households (offline sync)",
    openapi_extra=_bulk_household_openapi,
)
async def bulk_create_households(
    bulk_request: BulkHouseholdCreateRequest = Depends(_parse_bulk_household_create_request),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_field_roles)),
) -> BulkUploadResult:
    """
    Submit up to **500 households** in a single request.
    Each household goes through the same duplicate-check logic.
    Duplicates are skipped (not errored).
    For multipart uploads, send a `payload` JSON string and attach files as
    `landmark_images_<index>` where `<index>` is the household position.
    """
    return await HouseholdService(db).bulk_create_households(
        bulk_request.payload,
        current_user,
        landmark_image_files_by_index=bulk_request.landmark_images_by_index,
    )


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
    "/collection-records",
    response_model=list[CollectionRecordRead],
    summary="Admin audit: list collected data across all users",
)
async def list_all_collection_records(
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, max_length=120),
    collector_id: UUID | None = Query(None),
    household_id: UUID | None = Query(None),
    record_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_admin_roles)),
) -> list[CollectionRecordRead]:
    records = await VerificationService(db).list_collection_records(
        limit=limit,
        offset=offset,
        search=search,
        collector_id=collector_id,
        household_id=household_id,
        record_id=record_id,
    )
    return [CollectionRecordRead.model_validate(record) for record in records]


@router.get(
    "/collection-records/export",
    summary="Admin export: download collected data as CSV",
)
async def export_collection_records(
    search: str | None = Query(None, max_length=120),
    collector_id: UUID | None = Query(None),
    household_id: UUID | None = Query(None),
    record_id: UUID | None = Query(None),
    limit: int = Query(5000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(*_admin_roles)),
) -> Response:
    service = VerificationService(db)
    records = await service.list_collection_records(
        limit=limit,
        offset=0,
        search=search,
        collector_id=collector_id,
        household_id=household_id,
        record_id=record_id,
    )
    csv_content = service.export_collection_records_csv(records)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="collection-records.csv"',
        },
    )
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
    current_user: User = Depends(require_roles(*_admin_roles)),
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





