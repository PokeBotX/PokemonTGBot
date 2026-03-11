"""Async PostgreSQL database layer."""
import os
from pathlib import Path
from typing import Optional

import asyncpg
import structlog

logger = structlog.get_logger()


class Database:
    """Minimal asyncpg pool manager for bot data."""

    def __init__(self, dsn: Optional[str] = None) -> None:
        self.dsn = dsn or os.getenv("DATABASE_URL")
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Create connection pool."""
        if self.pool:
            return

        if self.dsn:
            self.pool = await asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=10)
        else:
            self.pool = await asyncpg.create_pool(
                host=os.getenv("DB_HOST", "127.0.0.1"),
                port=int(os.getenv("DB_PORT", "5432")),
                database=_required_env("DB_NAME"),
                user=_required_env("DB_USER"),
                password=_required_env("DB_PASSWORD"),
                min_size=1,
                max_size=10,
            )

        logger.info("db_connected")

    async def close(self) -> None:
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("db_closed")

    async def init_schema(self, schema_path: str = "sql/schema.sql") -> None:
        """Apply SQL schema from file."""
        self._ensure_pool()
        sql_text = Path(schema_path).read_text(encoding="utf-8")
        async with self.pool.acquire() as conn:
            await conn.execute(sql_text)
        logger.info("db_schema_applied", schema_path=schema_path)

    async def get_or_create_user(self, telegram_id: int, username: Optional[str]) -> int:
        """Create/update user by telegram_id and return internal id."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                WITH upserted_user AS (
                    INSERT INTO users (tg_user_id, nickname)
                    VALUES ($1, $2)
                    ON CONFLICT (tg_user_id)
                    DO UPDATE SET nickname = EXCLUDED.nickname
                    RETURNING id
                ),
                ensured_settings AS (
                    INSERT INTO user_settings (user_id)
                    SELECT id FROM upserted_user
                    ON CONFLICT (user_id) DO NOTHING
                )
                SELECT id FROM upserted_user;
                """,
                telegram_id,
                username,
            )
            return int(row["id"])

    def _ensure_pool(self) -> None:
        if not self.pool:
            raise RuntimeError("Database is not connected")


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required when DATABASE_URL is not set")
    return value
