import os
from typing import Optional

import asyncpg
from dotenv import load_dotenv


load_dotenv("poke.env")


def _env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Не задана переменная окружения: {name}")
    return value


class Database:
    def __init__(self) -> None:
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            host=_env("DB_HOST"),
            port=int(os.getenv("DB_PORT", 5432)),
            database=_env("DB_NAME"),
            user=_env("DB_USER"),
            password=_env("DB_PASSWORD"),
            min_size=1,
            max_size=10,
        )

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def init_schema(self) -> None:
        if not self.pool:
            raise RuntimeError("Сначала вызови connect()")

        schema_sql = """
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS currencies (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_wallets (
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            currency_code TEXT NOT NULL REFERENCES currencies(code),
            amount BIGINT NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, currency_code)
        );

        CREATE TABLE IF NOT EXISTS pokemon_species (
            id BIGSERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            rarity TEXT NOT NULL DEFAULT 'common'
        );

        CREATE TABLE IF NOT EXISTS user_pokemons (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            species_id BIGINT NOT NULL REFERENCES pokemon_species(id),
            level INT NOT NULL DEFAULT 1,
            captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """

        async with self.pool.acquire() as conn:
            await conn.execute(schema_sql)
            await conn.execute(
                """
                ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_id BIGINT;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
                ALTER TABLE users ADD COLUMN IF NOT EXISTS tg_user_id BIGINT;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS tg_username TEXT;

                UPDATE users
                SET telegram_id = COALESCE(telegram_id, tg_user_id, id);

                UPDATE users
                SET tg_user_id = COALESCE(tg_user_id, telegram_id, id);

                UPDATE users
                SET username = COALESCE(username, tg_username);

                UPDATE users
                SET tg_username = COALESCE(tg_username, username);

                ALTER TABLE users ALTER COLUMN telegram_id SET NOT NULL;
                CREATE UNIQUE INDEX IF NOT EXISTS users_telegram_id_uidx ON users (telegram_id);
                """
            )
            await conn.execute(
                """
                INSERT INTO currencies(code, name)
                VALUES ('pokedollar', 'PokéDollar'),
                       ('pokecoin', 'PokéCoin')
                ON CONFLICT (code) DO NOTHING;
                """
            )

    async def get_or_create_user(self, telegram_id: int, username: Optional[str]) -> int:
        if not self.pool:
            raise RuntimeError("Сначала вызови connect()")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO users (telegram_id, username, tg_user_id, tg_username)
                VALUES ($1, $2, $1, $2)
                ON CONFLICT (telegram_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    tg_user_id = EXCLUDED.tg_user_id,
                    tg_username = EXCLUDED.tg_username
                RETURNING id;
                """,
                telegram_id,
                username,
            )
            return int(row["id"])

    async def add_balance(self, user_id: int, currency_code: str, delta: int) -> None:
        if not self.pool:
            raise RuntimeError("Сначала вызови connect()")

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_wallets (user_id, currency_code, amount)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, currency_code)
                DO UPDATE SET amount = user_wallets.amount + EXCLUDED.amount;
                """,
                user_id,
                currency_code,
                delta,
            )

    async def get_balances(self, user_id: int) -> dict[str, int]:
        if not self.pool:
            raise RuntimeError("Сначала вызови connect()")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT currency_code, amount
                FROM user_wallets
                WHERE user_id = $1
                ORDER BY currency_code;
                """,
                user_id,
            )
            return {row["currency_code"]: row["amount"] for row in rows}

    async def add_species_if_missing(self, name: str, rarity: str = "common") -> int:
        if not self.pool:
            raise RuntimeError("Сначала вызови connect()")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO pokemon_species(name, rarity)
                VALUES ($1, $2)
                ON CONFLICT (name) DO UPDATE SET rarity = EXCLUDED.rarity
                RETURNING id;
                """,
                name,
                rarity,
            )
            return int(row["id"])

    async def catch_pokemon(self, user_id: int, species_id: int, level: int = 1) -> int:
        if not self.pool:
            raise RuntimeError("Сначала вызови connect()")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO user_pokemons(user_id, species_id, level)
                VALUES ($1, $2, $3)
                RETURNING id;
                """,
                user_id,
                species_id,
                level,
            )
            return int(row["id"])

    async def get_user_pokemon_count(self, user_id: int) -> int:
        if not self.pool:
            raise RuntimeError("Сначала вызови connect()")

        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM user_pokemons WHERE user_id = $1;",
                user_id,
            )
            return int(count or 0)
