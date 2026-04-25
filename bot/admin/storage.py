"""MinIO/S3 helpers for the admin bot."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Optional

import boto3

DEFAULT_BUCKET = "pokemon-assets"
DEFAULT_ENDPOINT = "http://127.0.0.1:9000"
DEFAULT_ACCESS_KEY = "minioadmin"
DEFAULT_SECRET_KEY = "minioadmin"
DEFAULT_PREFIX = "pokemon"
_NON_SLUG_RE = re.compile(r"[^a-z0-9._-]+")


def _slugify(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "-")
    normalized = _NON_SLUG_RE.sub("-", normalized)
    normalized = normalized.strip("-")
    return normalized or "asset"


def build_admin_object_key(*, pokemon_id: int, pokemon_name: str, file_unique_id: str, file_name: str | None) -> str:
    """Build a stable object key for one admin-uploaded pokemon art asset."""
    suffix = Path(file_name or "").suffix.lower()
    if not suffix:
        suffix = ".jpg"
    return (
        f"{os.getenv('S3_PREFIX', DEFAULT_PREFIX).strip('/')}/"
        f"{pokemon_id}/"
        f"{_slugify(pokemon_name)}-"
        f"{_slugify(file_unique_id)}{suffix}"
    )


def _build_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT_URL", DEFAULT_ENDPOINT),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID", DEFAULT_ACCESS_KEY),
        aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY", DEFAULT_SECRET_KEY),
    )


async def upload_admin_image_bytes(
    *,
    object_key: str,
    file_bytes: bytes,
    content_type: Optional[str],
) -> tuple[str, str, Optional[str]]:
    """Upload image bytes into the configured object storage."""
    bucket = os.getenv("S3_BUCKET", DEFAULT_BUCKET)

    def _upload() -> tuple[str, str, Optional[str]]:
        client = _build_s3_client()
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type
        response = client.put_object(
            Bucket=bucket,
            Key=object_key,
            Body=file_bytes,
            **extra_args,
        )
        etag = response.get("ETag")
        if isinstance(etag, str):
            etag = etag.strip('"')
        else:
            etag = None
        return bucket, object_key, etag

    return await asyncio.to_thread(_upload)
