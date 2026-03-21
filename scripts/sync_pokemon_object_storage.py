"""Upload local pokemon assets to MinIO and sync image credits in PostgreSQL."""

from __future__ import annotations

import argparse
import asyncio
import mimetypes
import os
from pathlib import Path
import subprocess
from typing import Iterable

import asyncpg

SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_BUCKET = "pokemon-assets"
DEFAULT_PREFIX = "pokemon"
DEFAULT_ENDPOINT = "http://127.0.0.1:9000"
DEFAULT_ACCESS_KEY = "minioadmin"
DEFAULT_SECRET_KEY = "minioadmin"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync pokemon art assets into object storage and image_credits")
    parser.add_argument("--assets-dir", default="assets/pokemon", help="Local pokemon assets directory")
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET", DEFAULT_BUCKET), help="Target S3 bucket")
    parser.add_argument("--prefix", default=os.getenv("S3_PREFIX", DEFAULT_PREFIX), help="Object key prefix")
    parser.add_argument(
        "--endpoint-url",
        default=os.getenv("S3_ENDPOINT_URL", DEFAULT_ENDPOINT),
        help="S3/MinIO endpoint URL",
    )
    parser.add_argument(
        "--access-key",
        default=os.getenv("S3_ACCESS_KEY_ID", DEFAULT_ACCESS_KEY),
        help="S3/MinIO access key",
    )
    parser.add_argument(
        "--secret-key",
        default=os.getenv("S3_SECRET_ACCESS_KEY", DEFAULT_SECRET_KEY),
        help="S3/MinIO secret key",
    )
    parser.add_argument("--skip-upload", action="store_true", help="Skip object upload and only sync DB metadata")
    parser.add_argument("--replace-catalog", action="store_true", help="Replace existing pokemon_catalog image links")
    return parser.parse_args()


def _load_dotenv() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required when DATABASE_URL is not set")
    return value


def _db_connect_kwargs() -> dict[str, object]:
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return {"dsn": dsn}
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "database": _required_env("DB_NAME"),
        "user": _required_env("DB_USER"),
        "password": _required_env("DB_PASSWORD"),
    }


def _iter_pokemon_images(assets_dir: Path) -> Iterable[tuple[str, Path]]:
    for pokemon_dir in sorted(path for path in assets_dir.iterdir() if path.is_dir()):
        files = sorted(
            path for path in pokemon_dir.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
        )
        for file_path in files:
            yield pokemon_dir.name, file_path


def _object_key(prefix: str, pokemon_name: str, file_path: Path) -> str:
    return f"{prefix.rstrip('/')}/{pokemon_name}/{file_path.name}"


def _source_path(file_path: Path) -> str:
    if file_path.is_absolute():
        try:
            return str(file_path.relative_to(Path.cwd()))
        except ValueError:
            return str(file_path)
    return str(file_path)


def _run_mc_command(*args: str, assets_dir: Path | None = None) -> None:
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "host",
        "-e",
        f"MC_HOST_local={DEFAULT_ENDPOINT}",
    ]
    if assets_dir is not None:
        command.extend(["-v", f"{assets_dir.resolve()}:/assets:ro"])
    command.extend(args)
    subprocess.run(command, check=True)


def upload_assets(
    *,
    assets_dir: Path,
    bucket: str,
    prefix: str,
    endpoint_url: str,
    access_key: str,
    secret_key: str,
) -> None:
    mc_host = f"MC_HOST_local={endpoint_url.rstrip('/').replace('://', f'://{access_key}:{secret_key}@')}"
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "host",
            "-e",
            mc_host,
            "minio/mc",
            "mb",
            "--ignore-existing",
            f"local/{bucket}",
        ],
        check=True,
    )
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "host",
            "-e",
            mc_host,
            "-v",
            f"{assets_dir.resolve()}:/assets:ro",
            "minio/mc",
            "anonymous",
            "set",
            "download",
            f"local/{bucket}",
        ],
        check=True,
    )
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "host",
            "-e",
            mc_host,
            "-v",
            f"{assets_dir.resolve()}:/assets:ro",
            "minio/mc",
            "mirror",
            "--overwrite",
            "/assets",
            f"local/{bucket}/{prefix}",
        ],
        check=True,
    )


async def sync_db(
    *,
    assets_dir: Path,
    bucket: str,
    prefix: str,
    replace_catalog: bool,
) -> tuple[int, int, list[str]]:
    file_rows: list[tuple[str, Path]] = list(_iter_pokemon_images(assets_dir))
    if not file_rows:
        return 0, 0, []

    conn = await asyncpg.connect(**_db_connect_kwargs())
    synced_image_credits = 0
    linked_catalog = 0
    missing_catalog: list[str] = []
    primary_ids: dict[str, int] = {}
    try:
        async with conn.transaction():
            for pokemon_name, file_path in file_rows:
                object_key = _object_key(prefix, pokemon_name, file_path)
                content_type = mimetypes.guess_type(file_path.name)[0]
                image_credit_id = await conn.fetchval(
                    """
                    INSERT INTO image_credits (
                      storage_bucket,
                      object_key,
                      content_type,
                      source,
                      author
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (storage_bucket, object_key) DO UPDATE
                    SET content_type = EXCLUDED.content_type,
                        source = EXCLUDED.source
                    RETURNING id
                    """,
                    bucket,
                    object_key,
                    content_type,
                    _source_path(file_path),
                    "pokemonbot-assets",
                )
                synced_image_credits += 1
                primary_ids.setdefault(pokemon_name, int(image_credit_id))

            for pokemon_name, image_credit_id in sorted(primary_ids.items()):
                sql = """
                    UPDATE pokemon_catalog
                    SET image_credit_id = $2
                    WHERE name = $1
                """
                if not replace_catalog:
                    sql += " AND image_credit_id IS NULL"
                result = await conn.execute(sql, pokemon_name, image_credit_id)
                updated = int(result.split()[-1])
                if updated:
                    linked_catalog += updated
                else:
                    exists = await conn.fetchval(
                        "SELECT 1 FROM pokemon_catalog WHERE name = $1 LIMIT 1",
                        pokemon_name,
                    )
                    if not exists:
                        missing_catalog.append(pokemon_name)
    finally:
        await conn.close()

    return synced_image_credits, linked_catalog, missing_catalog


async def main() -> None:
    _load_dotenv()
    args = parse_args()
    assets_dir = Path(args.assets_dir)
    if not assets_dir.exists():
        raise FileNotFoundError(f"Assets directory not found: {assets_dir}")

    if not args.skip_upload:
        upload_assets(
            assets_dir=assets_dir,
            bucket=args.bucket,
            prefix=args.prefix,
            endpoint_url=args.endpoint_url,
            access_key=args.access_key,
            secret_key=args.secret_key,
        )

    synced_image_credits, linked_catalog, missing_catalog = await sync_db(
        assets_dir=assets_dir,
        bucket=args.bucket,
        prefix=args.prefix,
        replace_catalog=args.replace_catalog,
    )

    print(f"Synced image_credits: {synced_image_credits}")
    print(f"Linked pokemon_catalog rows: {linked_catalog}")
    if missing_catalog:
        print(f"Missing pokemon_catalog rows: {len(missing_catalog)}")
        for name in missing_catalog[:20]:
            print(f"- {name}")


if __name__ == "__main__":
    asyncio.run(main())
