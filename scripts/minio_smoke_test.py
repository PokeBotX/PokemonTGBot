"""Small local MinIO smoke test for listing bucket contents."""

from __future__ import annotations

import os

import boto3


def main() -> None:
    bucket = os.getenv("S3_BUCKET", "pokemon-assets")
    endpoint_url = os.getenv("S3_ENDPOINT_URL", "http://127.0.0.1:9000")
    access_key = os.getenv("S3_ACCESS_KEY_ID", "minioadmin")
    secret_key = os.getenv("S3_SECRET_ACCESS_KEY", "minioadmin")

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )

    response = s3.list_objects_v2(Bucket=bucket)
    objects = response.get("Contents", [])

    print(f"Bucket: {bucket}")
    print(f"Objects: {len(objects)}")
    for obj in objects:
        print(f"- key={obj['Key']} size={obj['Size']} etag={obj['ETag']}")


if __name__ == "__main__":
    main()
