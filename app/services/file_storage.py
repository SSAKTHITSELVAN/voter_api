import contextlib
from pathlib import Path
from uuid import UUID, uuid4

import aiofiles
from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings

settings = get_settings()

_CONTENT_TYPE_TO_EXTENSION = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
}
_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


class FileStorageService:
    def __init__(self) -> None:
        self._root = Path(settings.UPLOAD_DIR).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    async def save_household_images(
        self,
        household_id: UUID,
        files: list[UploadFile],
    ) -> list[str]:
        if len(files) > settings.HOUSEHOLD_IMAGE_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Maximum {settings.HOUSEHOLD_IMAGE_LIMIT} landmark images "
                    "allowed per household."
                ),
            )

        target_dir = self._root / "households" / str(household_id)
        target_dir.mkdir(parents=True, exist_ok=True)

        saved_paths: list[Path] = []
        saved_urls: list[str] = []

        try:
            for upload in files:
                extension = self._resolve_extension(upload)
                filename = f"{uuid4()}{extension}"
                destination = target_dir / filename

                async with aiofiles.open(destination, "wb") as buffer:
                    while chunk := await upload.read(1024 * 1024):
                        await buffer.write(chunk)

                saved_paths.append(destination)
                saved_urls.append(
                    f"{settings.UPLOAD_URL_PREFIX}/households/{household_id}/{filename}"
                )

            return saved_urls
        except Exception:
            self.delete_files(saved_paths)
            raise
        finally:
            await self.close_files(files)

    async def close_files(self, files: list[UploadFile]) -> None:
        for upload in files:
            with contextlib.suppress(Exception):
                await upload.close()

    def delete_urls(self, urls: list[str]) -> None:
        for url in urls:
            relative_path = url.removeprefix(settings.UPLOAD_URL_PREFIX).lstrip("/")
            if not relative_path:
                continue
            path = self._root / relative_path
            with contextlib.suppress(FileNotFoundError):
                path.unlink()
            self._cleanup_empty_parents(path.parent)

    def delete_files(self, paths: list[Path]) -> None:
        for path in paths:
            with contextlib.suppress(FileNotFoundError):
                path.unlink()
            self._cleanup_empty_parents(path.parent)

    def _resolve_extension(self, upload: UploadFile) -> str:
        content_type = (upload.content_type or "").lower()
        if content_type and not content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Only image uploads are allowed for landmark_images.",
            )

        extension = Path(upload.filename or "").suffix.lower()
        if extension in _ALLOWED_EXTENSIONS:
            return ".jpg" if extension == ".jpeg" else extension

        mapped_extension = _CONTENT_TYPE_TO_EXTENSION.get(content_type)
        if mapped_extension:
            return mapped_extension

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Unsupported landmark image type. Use JPG, PNG, WEBP, GIF, or BMP."
            ),
        )

    def _cleanup_empty_parents(self, directory: Path) -> None:
        households_root = self._root / "households"
        current = directory
        while current != self._root and current != households_root.parent:
            if current == households_root:
                break
            with contextlib.suppress(OSError):
                current.rmdir()
            current = current.parent
