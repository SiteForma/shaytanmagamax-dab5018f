from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from apps.api.app.core.config import Settings


@dataclass(slots=True)
class StoredObject:
    storage_key: str
    checksum: str
    size_bytes: int
    content_type: str


class ObjectStorage:
    def save_upload(self, upload: UploadFile) -> StoredObject:
        raise NotImplementedError

    def load_upload_bytes(self, storage_key: str) -> bytes:
        raise NotImplementedError

    def resolve_path(self, storage_key: str) -> Path:
        raise NotImplementedError

    def healthcheck(self) -> tuple[bool, str]:
        raise NotImplementedError


class LocalObjectStorage(ObjectStorage):
    def __init__(self, settings: Settings) -> None:
        self._root = Path(settings.local_object_storage_root)
        self._root.mkdir(parents=True, exist_ok=True)

    def save_upload(self, upload: UploadFile) -> StoredObject:
        payload = upload.file.read()
        checksum = hashlib.sha256(payload).hexdigest()
        safe_name = (upload.filename or "upload.bin").replace("/", "_")
        storage_key = f"uploads/{checksum[:10]}_{safe_name}"
        file_path = self.resolve_path(storage_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(payload)
        return StoredObject(
            storage_key=storage_key,
            checksum=checksum,
            size_bytes=len(payload),
            content_type=upload.content_type or "application/octet-stream",
        )

    def resolve_path(self, storage_key: str) -> Path:
        return self._root / storage_key

    def load_upload_bytes(self, storage_key: str) -> bytes:
        return self.resolve_path(storage_key).read_bytes()

    def healthcheck(self) -> tuple[bool, str]:
        try:
            probe_path = self._root / ".healthcheck"
            self._root.mkdir(parents=True, exist_ok=True)
            probe_path.write_text("ok", encoding="utf-8")
            probe_path.unlink(missing_ok=True)
            return True, str(self._root)
        except Exception as exc:
            return False, str(exc)


class S3ObjectStorage(ObjectStorage):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        try:
            import boto3  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise RuntimeError("boto3 is required for s3 object storage mode") from exc
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._settings.s3_bucket)
        except Exception:
            self._client.create_bucket(Bucket=self._settings.s3_bucket)

    def save_upload(self, upload: UploadFile) -> StoredObject:
        payload = upload.file.read()
        checksum = hashlib.sha256(payload).hexdigest()
        safe_name = (upload.filename or "upload.bin").replace("/", "_")
        storage_key = f"uploads/{checksum[:10]}_{safe_name}"
        self._client.put_object(
            Bucket=self._settings.s3_bucket,
            Key=storage_key,
            Body=payload,
            ContentType=upload.content_type or "application/octet-stream",
        )
        return StoredObject(
            storage_key=storage_key,
            checksum=checksum,
            size_bytes=len(payload),
            content_type=upload.content_type or "application/octet-stream",
        )

    def resolve_path(self, storage_key: str) -> Path:
        raise NotImplementedError("S3 object storage does not expose a local filesystem path")

    def load_upload_bytes(self, storage_key: str) -> bytes:
        response = self._client.get_object(Bucket=self._settings.s3_bucket, Key=storage_key)
        return response["Body"].read()

    def healthcheck(self) -> tuple[bool, str]:
        try:
            self._client.head_bucket(Bucket=self._settings.s3_bucket)
            return True, self._settings.s3_bucket
        except Exception as exc:
            return False, str(exc)


def get_object_storage(settings: Settings) -> ObjectStorage:
    if settings.object_storage_mode == "local":
        return LocalObjectStorage(settings)
    return S3ObjectStorage(settings)
