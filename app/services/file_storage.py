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
        import logging
        self._logger = logging.getLogger(__name__)
        self._root = Path(settings.UPLOAD_DIR).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        
        # Initialize S3 client if enabled
        self._s3_client = None
        if settings.USE_S3_ENABLED:
            try:
                import boto3
                self._logger.info("S3 enabled, initializing S3 client...")
                self._logger.info(f"Bucket: {settings.AWS_S3_BUCKET}, Region: {settings.AWS_S3_REGION}")
                
                # Check if credentials are set
                if not settings.AWS_ACCESS_KEY_ID or settings.AWS_ACCESS_KEY_ID == "":
                    self._logger.error("AWS_ACCESS_KEY_ID is empty!")
                if not settings.AWS_SECRET_ACCESS_KEY or settings.AWS_SECRET_ACCESS_KEY == "":
                    self._logger.error("AWS_SECRET_ACCESS_KEY is empty!")
                
                self._s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=settings.AWS_S3_REGION,
                )
                self._logger.info("✓ S3 client initialized successfully")
            except Exception as e:
                self._logger.error(f"✗ Failed to initialize S3 client: {str(e)}")
                self._s3_client = None

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

        saved_urls: list[str] = []

        try:
            for upload in files:
                extension = self._resolve_extension(upload)
                filename = f"{uuid4()}{extension}"
                
                if self._s3_client and settings.USE_S3_ENABLED:
                    # Upload to S3
                    url = await self._save_to_s3(household_id, filename, upload)
                else:
                    # Upload to local storage
                    url = await self._save_to_local(household_id, filename, upload)
                
                saved_urls.append(url)

            return saved_urls
        except Exception:
            await self.close_files(files)
            raise
        finally:
            await self.close_files(files)

    async def _save_to_s3(self, household_id: UUID, filename: str, upload: UploadFile) -> str:
        """Upload file to S3 and return the URL"""
        try:
            self._logger.info(f"Attempting to upload to S3: {filename}")
            file_content = await upload.read()
            s3_key = f"households/{household_id}/{filename}"
            
            self._s3_client.put_object(
                Bucket=settings.AWS_S3_BUCKET,
                Key=s3_key,
                Body=file_content,
                ContentType=upload.content_type or "image/jpeg",
            )
            
            # Generate S3 URL
            url = f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_S3_REGION}.amazonaws.com/{s3_key}"
            self._logger.info(f"✓ Successfully uploaded to S3: {url}")
            return url
        except Exception as e:
            self._logger.error(f"✗ S3 upload failed: {str(e)}, falling back to local storage")
            # Fall back to local storage if S3 fails
            return await self._save_to_local(household_id, filename, upload)

    async def _save_to_local(self, household_id: UUID, filename: str, upload: UploadFile) -> str:
        """Upload file to local storage and return the URL"""
        target_dir = self._root / "households" / str(household_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        
        destination = target_dir / filename
        
        async with aiofiles.open(destination, "wb") as buffer:
            while chunk := await upload.read(1024 * 1024):
                await buffer.write(chunk)
        
        return f"{settings.UPLOAD_URL_PREFIX}/households/{household_id}/{filename}"

    async def close_files(self, files: list[UploadFile]) -> None:
        for upload in files:
            with contextlib.suppress(Exception):
                await upload.close()

    def delete_urls(self, urls: list[str]) -> None:
        for url in urls:
            if url.startswith(f"https://{settings.AWS_S3_BUCKET}.s3."):
                # S3 URL - extract key and delete from S3
                self._delete_s3_files([url])
            else:
                # Local URL
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

    def _delete_s3_files(self, urls: list[str]) -> None:
        """Delete files from S3"""
        if not self._s3_client or not settings.USE_S3_ENABLED:
            return
        
        for url in urls:
            try:
                # Extract S3 key from URL
                prefix = f"https://{settings.AWS_S3_BUCKET}.s3.{settings.AWS_S3_REGION}.amazonaws.com/"
                if url.startswith(prefix):
                    s3_key = url[len(prefix):]
                    self._s3_client.delete_object(
                        Bucket=settings.AWS_S3_BUCKET,
                        Key=s3_key,
                    )
            except Exception:
                # Suppress S3 deletion errors
                pass

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
