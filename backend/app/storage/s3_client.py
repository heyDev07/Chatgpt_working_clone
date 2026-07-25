import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aioboto3

from app.config.settings import get_settings

_session = aioboto3.Session()

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def safe_storage_filename(filename: str) -> str:
    """Never trust a user-supplied filename as part of an object storage key - document_service
    and attachment_service both build keys as f"{user_id}/{id}/{filename}", and S3 doesn't
    resolve ".." specially (it's just a literal key), but a raw filename embedded there is still
    bad practice: it can produce keys with unexpected pseudo-directory structure, and would
    become a genuine path-traversal bug outright if storage ever moved to a real filesystem
    backend. Strips any directory components and anything outside a conservative allowlist; the
    original filename (used for display, e.g. MessageOut) is untouched."""
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = _UNSAFE_FILENAME_CHARS.sub("_", basename).strip("._")
    return cleaned[:200] or "file"


@asynccontextmanager
async def get_s3_client() -> AsyncIterator:
    settings = get_settings()
    async with _session.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    ) as client:
        yield client


async def ensure_bucket_exists() -> None:
    settings = get_settings()
    async with get_s3_client() as client:
        try:
            await client.head_bucket(Bucket=settings.s3_bucket)
        except Exception:
            await client.create_bucket(Bucket=settings.s3_bucket)


async def upload_bytes(key: str, data: bytes, content_type: str) -> None:
    settings = get_settings()
    async with get_s3_client() as client:
        await client.put_object(Bucket=settings.s3_bucket, Key=key, Body=data, ContentType=content_type)


async def download_bytes(key: str) -> bytes:
    settings = get_settings()
    async with get_s3_client() as client:
        response = await client.get_object(Bucket=settings.s3_bucket, Key=key)
        return await response["Body"].read()


async def delete_object(key: str) -> None:
    settings = get_settings()
    async with get_s3_client() as client:
        await client.delete_object(Bucket=settings.s3_bucket, Key=key)
