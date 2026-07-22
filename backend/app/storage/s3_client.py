from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aioboto3

from app.config.settings import get_settings

_session = aioboto3.Session()


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
