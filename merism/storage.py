"""Object storage client — uploads files to S3-compatible storage (MinIO in dev).

Usage:
    from merism.storage import upload_stimulus_file
    url = upload_stimulus_file(file, study_id="abc", filename="img.png")
"""

from __future__ import annotations

import os
import uuid
from typing import BinaryIO

import boto3
from botocore.config import Config


def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("OBJECT_STORAGE_ENDPOINT", "http://localhost:9100"),
        aws_access_key_id=os.environ.get("OBJECT_STORAGE_ACCESS_KEY", "merism"),
        aws_secret_access_key=os.environ.get("OBJECT_STORAGE_SECRET_KEY", "merism-dev-password"),
        region_name=os.environ.get("OBJECT_STORAGE_REGION", "us-east-1"),
        config=Config(signature_version="s3v4"),
    )


def _get_bucket() -> str:
    return os.environ.get("OBJECT_STORAGE_BUCKET", "merism-dev")


def ensure_bucket() -> None:
    """Create the bucket if it doesn't exist (dev convenience)."""
    client = _get_client()
    bucket = _get_bucket()
    try:
        client.head_bucket(Bucket=bucket)
    except client.exceptions.ClientError:
        client.create_bucket(Bucket=bucket)


def upload_stimulus_file(
    file: BinaryIO,
    *,
    study_id: str,
    filename: str,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload a file and return its public URL."""
    client = _get_client()
    bucket = _get_bucket()
    ensure_bucket()

    key = f"stimuli/{study_id}/{uuid.uuid4().hex[:8]}_{filename}"
    client.upload_fileobj(
        file,
        bucket,
        key,
        ExtraArgs={"ContentType": content_type},
    )

    endpoint = os.environ.get("OBJECT_STORAGE_ENDPOINT", "http://localhost:9100")
    return f"{endpoint}/{bucket}/{key}"
