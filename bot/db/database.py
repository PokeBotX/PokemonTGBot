"""Async PostgreSQL database layer."""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional, Sequence

import asyncpg
import structlog

logger = structlog.get_logger()

POKEDOLLAR_CODE = "pokedollar"
POKECOIN_CODE = "pokecoin"
SHOP_BONUS_CAP = 750
SHOP_BONUS_RATE_PER_HOUR = 125
SHOP_BONUS_CLAIM_INTERVAL_SECONDS = 3600
SHOP_BONUS_CAP_SECONDS = 6 * 3600
SPIN_PRICE = 500
ULTRABALL_PRICE = 200
MASTERBALL_PRICE = 1000
EPIC_PITY_THRESHOLD = 15
LEGENDARY_PITY_THRESHOLD = 40
RARITY_PROBABILITIES = {
    "Legendary": 2.0,
    "Epic": 7.5,
    "Rare": 20.2,
    "Common": 70.3,
}
RARITY_ORDER = ("Legendary", "Epic", "Rare", "Common")


class ShopError(RuntimeError):
    """Base class for shop-related failures."""


class ShopUnavailableError(ShopError):
    """Raised when the database-backed shop is unavailable."""


class InsufficientFundsError(ShopError):
    """Raised when the user cannot afford an action."""


class BonusNotReadyError(ShopError):
    """Raised when the daily bonus is still on cooldown."""

    def __init__(self, remaining_seconds: int) -> None:
        self.remaining_seconds = remaining_seconds
        super().__init__("Bonus claim is not ready yet")


class SummarySessionError(ShopError):
    """Raised when a stored x5 result summary is unavailable."""


@dataclass(slots=True)
class ShopView:
    """Shop screen state for a user."""

    user_id: int
    balance: int
    pokecoin_balance: int
    ultraball_quantity: int
    masterball_quantity: int
    epic_pity_counter: int
    legendary_pity_counter: int
    bonus_available: int
    bonus_ready_in_seconds: int


@dataclass(slots=True)
class BonusClaimResult:
    """Result of claiming the daily bonus."""

    amount_claimed: int
    next_bonus_in_seconds: int
    shop_view: ShopView


@dataclass(slots=True)
class ItemPurchaseResult:
    """Result of purchasing one shop item."""

    item_code: str
    item_name: str
    item_price: int
    quantity_after: int
    shop_view: ShopView


@dataclass(slots=True)
class PokemonReward:
    """A user-owned pokemon obtained from the shop gacha."""

    user_pokemon_id: int
    pokemon_id: int
    name: str
    rarity: str
    pokemon_type: Optional[str]
    base_hp: int
    base_attack: int
    base_defense: int
    base_stamina: int
    image_credit_id: Optional[int]

    def as_session_payload(self) -> dict[str, object]:
        """Convert reward to a JSON-like payload for in-memory sessions."""
        return {
            "user_pokemon_id": self.user_pokemon_id,
            "pokemon_id": self.pokemon_id,
            "name": self.name,
            "rarity": self.rarity,
            "pokemon_type": self.pokemon_type,
            "base_hp": self.base_hp,
            "base_attack": self.base_attack,
            "base_defense": self.base_defense,
            "base_stamina": self.base_stamina,
            "image_credit_id": self.image_credit_id,
        }


@dataclass(slots=True)
class SpinResult:
    """Outcome of one or multiple shop spins."""

    rewards: list[PokemonReward]
    spent_amount: int
    shop_view: ShopView


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
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
        return user_id

    async def get_shop_view(self, telegram_id: int, username: Optional[str]) -> ShopView:
        """Load shop data for the current user."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                return await self._fetch_shop_view(conn, user_id)

    async def claim_daily_bonus(self, telegram_id: int, username: Optional[str]) -> BonusClaimResult:
        """Claim the accumulated daily bonus if it is ready."""
        self._ensure_pool()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                state = await self._fetch_shop_state_row(conn, user_id, for_update=True)
                now = datetime.now(UTC)
                amount = _calculate_bonus_amount(state["bonus_last_claim_at"], now)
                if amount < SHOP_BONUS_RATE_PER_HOUR:
                    raise BonusNotReadyError(
                        remaining_seconds=_bonus_remaining_seconds(state["bonus_last_claim_at"], now)
                    )

                await self._adjust_balance(conn, user_id, POKEDOLLAR_CODE, amount)
                await conn.execute(
                    """
                    UPDATE user_shop_state
                    SET bonus_last_claim_at = $2,
                        updated_at = $2
                    WHERE user_id = $1
                    """,
                    user_id,
                    now,
                )
                shop_view = await self._fetch_shop_view(conn, user_id)

        logger.info("shop_bonus_claimed", telegram_id=telegram_id, amount=amount)
        return BonusClaimResult(
            amount_claimed=amount,
            next_bonus_in_seconds=SHOP_BONUS_CLAIM_INTERVAL_SECONDS,
            shop_view=shop_view,
        )

    async def purchase_item(
        self, telegram_id: int, username: Optional[str], item_code: str
    ) -> ItemPurchaseResult:
        """Purchase one shop item."""
        self._ensure_pool()
        if item_code not in {"ultraball", "masterball"}:
            raise ShopError(f"Unsupported item: {item_code}")

        item_price = ULTRABALL_PRICE if item_code == "ultraball" else MASTERBALL_PRICE
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                await self._ensure_user_balance(conn, user_id, POKEDOLLAR_CODE)
                await self._ensure_shop_state(conn, user_id)
                balance = await self._get_balance_for_update(conn, user_id, POKEDOLLAR_CODE)
                if balance < item_price:
                    raise InsufficientFundsError("Not enough pokedollar")

                item_row = await conn.fetchrow(
                    "SELECT id, name FROM items WHERE code = $1",
                    item_code,
                )
                if not item_row:
                    raise ShopError(f"Item seed missing for {item_code}")

                await conn.execute(
                    """
                    UPDATE user_balances
                    SET amount = amount - $3
                    WHERE user_id = $1 AND currency_id = $2
                    """,
                    user_id,
                    await self._get_currency_id(conn, POKEDOLLAR_CODE),
                    item_price,
                )
                await conn.execute(
                    """
                    INSERT INTO user_items (user_id, item_id, quantity)
                    VALUES ($1, $2, 1)
                    ON CONFLICT (user_id, item_id)
                    DO UPDATE SET quantity = user_items.quantity + 1
                    """,
                    user_id,
                    int(item_row["id"]),
                )
                quantity_after = await conn.fetchval(
                    "SELECT quantity FROM user_items WHERE user_id = $1 AND item_id = $2",
                    user_id,
                    int(item_row["id"]),
                )
                shop_view = await self._fetch_shop_view(conn, user_id)

        logger.info(
            "shop_item_purchased",
            telegram_id=telegram_id,
            item_code=item_code,
            price=item_price,
        )
        return ItemPurchaseResult(
            item_code=item_code,
            item_name=str(item_row["name"]),
            item_price=item_price,
            quantity_after=int(quantity_after),
            shop_view=shop_view,
        )

    async def spin_gacha(
        self, telegram_id: int, username: Optional[str], spin_count: int
    ) -> SpinResult:
        """Perform one or multiple gacha spins."""
        self._ensure_pool()
        if spin_count not in {1, 5}:
            raise ShopError("Only x1 and x5 spins are supported")

        total_cost = SPIN_PRICE * spin_count
        rewards: list[PokemonReward] = []

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user_id = await self._ensure_user(conn, telegram_id, username)
                await self._ensure_user_balance(conn, user_id, POKEDOLLAR_CODE)
                state = await self._fetch_shop_state_row(conn, user_id, for_update=True)
                balance = await self._get_balance_for_update(conn, user_id, POKEDOLLAR_CODE)
                if balance < total_cost:
                    raise InsufficientFundsError("Not enough pokedollar")

                await conn.execute(
                    """
                    UPDATE user_balances
                    SET amount = amount - $3
                    WHERE user_id = $1 AND currency_id = $2
                    """,
                    user_id,
                    await self._get_currency_id(conn, POKEDOLLAR_CODE),
                    total_cost,
                )

                epic_counter = int(state["epic_pity_counter"])
                legendary_counter = int(state["legendary_pity_counter"])
                for _ in range(spin_count):
                    reward = await self._draw_pokemon_reward(conn, user_id, epic_counter, legendary_counter)
                    rewards.append(reward)
                    epic_counter, legendary_counter = _update_pity_counters(
                        reward.rarity,
                        epic_counter,
                        legendary_counter,
                    )

                await conn.execute(
                    """
                    UPDATE user_shop_state
                    SET epic_pity_counter = $2,
                        legendary_pity_counter = $3,
                        updated_at = $4
                    WHERE user_id = $1
                    """,
                    user_id,
                    epic_counter,
                    legendary_counter,
                    datetime.now(UTC),
                )
                shop_view = await self._fetch_shop_view(conn, user_id)

        logger.info(
            "shop_spin_completed",
            telegram_id=telegram_id,
            spin_count=spin_count,
            spent_amount=total_cost,
            rewards=[reward.rarity for reward in rewards],
        )
        return SpinResult(rewards=rewards, spent_amount=total_cost, shop_view=shop_view)

    def _ensure_pool(self) -> None:
        if not self.pool:
            raise ShopUnavailableError("Database is not connected")

    async def _ensure_user(
        self, conn: asyncpg.Connection, telegram_id: int, username: Optional[str]
    ) -> int:
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
            ),
            ensured_shop_state AS (
                INSERT INTO user_shop_state (user_id)
                SELECT id FROM upserted_user
                ON CONFLICT (user_id) DO NOTHING
            ),
            ensured_balance AS (
                INSERT INTO user_balances (user_id, currency_id, amount)
                SELECT upserted_user.id, currencies.id, 0
                FROM upserted_user
                JOIN currencies ON currencies.code = $3
                ON CONFLICT (user_id, currency_id) DO NOTHING
            )
            SELECT id FROM upserted_user;
            """,
            telegram_id,
            username,
            POKEDOLLAR_CODE,
        )
        if not row:
            raise ShopError("Unable to ensure user record")
        return int(row["id"])

    async def _ensure_shop_state(self, conn: asyncpg.Connection, user_id: int) -> None:
        await conn.execute(
            """
            INSERT INTO user_shop_state (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
        )

    async def _ensure_user_balance(
        self, conn: asyncpg.Connection, user_id: int, currency_code: str
    ) -> None:
        await conn.execute(
            """
            INSERT INTO user_balances (user_id, currency_id, amount)
            VALUES ($1, $2, 0)
            ON CONFLICT (user_id, currency_id) DO NOTHING
            """,
            user_id,
            await self._get_currency_id(conn, currency_code),
        )

    async def _get_currency_id(self, conn: asyncpg.Connection, code: str) -> int:
        currency_id = await conn.fetchval("SELECT id FROM currencies WHERE code = $1", code)
        if currency_id is None:
            raise ShopError(f"Currency seed missing for {code}")
        return int(currency_id)

    async def _fetch_shop_state_row(
        self, conn: asyncpg.Connection, user_id: int, *, for_update: bool = False
    ) -> asyncpg.Record:
        await self._ensure_shop_state(conn, user_id)
        lock_clause = " FOR UPDATE" if for_update else ""
        row = await conn.fetchrow(
            (
                "SELECT user_id, bonus_last_claim_at, epic_pity_counter, legendary_pity_counter "
                "FROM user_shop_state WHERE user_id = $1" + lock_clause
            ),
            user_id,
        )
        if not row:
            raise ShopError("Shop state is missing")
        return row

    async def _fetch_shop_view(self, conn: asyncpg.Connection, user_id: int) -> ShopView:
        await self._ensure_shop_state(conn, user_id)
        await self._ensure_user_balance(conn, user_id, POKEDOLLAR_CODE)
        row = await conn.fetchrow(
            """
            SELECT
              uss.user_id,
              uss.bonus_last_claim_at,
              uss.epic_pity_counter,
              uss.legendary_pity_counter,
              COALESCE((
                SELECT ub.amount
                FROM user_balances ub
                JOIN currencies c ON c.id = ub.currency_id
                WHERE ub.user_id = uss.user_id AND c.code = 'pokedollar'
              ), 0) AS balance,
              COALESCE((
                SELECT ub.amount
                FROM user_balances ub
                JOIN currencies c ON c.id = ub.currency_id
                WHERE ub.user_id = uss.user_id AND c.code = 'pokecoin'
              ), 0) AS pokecoin_balance,
              COALESCE((
                SELECT ui.quantity
                FROM user_items ui
                JOIN items i ON i.id = ui.item_id
                WHERE ui.user_id = uss.user_id AND i.code = 'ultraball'
              ), 0) AS ultraball_quantity,
              COALESCE((
                SELECT ui.quantity
                FROM user_items ui
                JOIN items i ON i.id = ui.item_id
                WHERE ui.user_id = uss.user_id AND i.code = 'masterball'
              ), 0) AS masterball_quantity
            FROM user_shop_state uss
            WHERE uss.user_id = $1
            """,
            user_id,
        )
        if not row:
            raise ShopError("Unable to fetch shop view")

        now = datetime.now(UTC)
        bonus_available = _calculate_bonus_amount(row["bonus_last_claim_at"], now)
        bonus_ready_in_seconds = _bonus_remaining_seconds(row["bonus_last_claim_at"], now)
        return ShopView(
            user_id=int(row["user_id"]),
            balance=int(row["balance"]),
            pokecoin_balance=int(row["pokecoin_balance"]),
            ultraball_quantity=int(row["ultraball_quantity"]),
            masterball_quantity=int(row["masterball_quantity"]),
            epic_pity_counter=int(row["epic_pity_counter"]),
            legendary_pity_counter=int(row["legendary_pity_counter"]),
            bonus_available=bonus_available,
            bonus_ready_in_seconds=bonus_ready_in_seconds,
        )

    async def _get_balance_for_update(
        self, conn: asyncpg.Connection, user_id: int, currency_code: str
    ) -> int:
        row = await conn.fetchrow(
            """
            SELECT ub.amount
            FROM user_balances ub
            JOIN currencies c ON c.id = ub.currency_id
            WHERE ub.user_id = $1 AND c.code = $2
            FOR UPDATE
            """,
            user_id,
            currency_code,
        )
        if not row:
            return 0
        return int(row["amount"])

    async def _adjust_balance(
        self, conn: asyncpg.Connection, user_id: int, currency_code: str, delta: int
    ) -> None:
        await self._ensure_user_balance(conn, user_id, currency_code)
        await conn.execute(
            """
            UPDATE user_balances
            SET amount = amount + $3
            WHERE user_id = $1 AND currency_id = $2
            """,
            user_id,
            await self._get_currency_id(conn, currency_code),
            delta,
        )

    async def _draw_pokemon_reward(
        self,
        conn: asyncpg.Connection,
        user_id: int,
        epic_counter: int,
        legendary_counter: int,
    ) -> PokemonReward:
        reward_rarity = _resolve_roll_rarity(epic_counter, legendary_counter)
        pokemon_row = await self._select_random_pokemon(conn, reward_rarity)
        inserted = await conn.fetchrow(
            """
            INSERT INTO user_pokemon (owner_user_id, pokemon_id)
            VALUES ($1, $2)
            RETURNING id
            """,
            user_id,
            int(pokemon_row["id"]),
        )
        return PokemonReward(
            user_pokemon_id=int(inserted["id"]),
            pokemon_id=int(pokemon_row["id"]),
            name=str(pokemon_row["name"]),
            rarity=str(pokemon_row["rarity"]),
            pokemon_type=pokemon_row["type"],
            base_hp=int(pokemon_row["base_hp"]),
            base_attack=int(pokemon_row["base_attack"]),
            base_defense=int(pokemon_row["base_defense"]),
            base_stamina=int(pokemon_row["base_stamina"]),
            image_credit_id=pokemon_row["image_credit_id"],
        )

    async def _select_random_pokemon(
        self, conn: asyncpg.Connection, target_rarity: str
    ) -> asyncpg.Record:
        rarities = _rarity_pool_for_target(target_rarity)
        row = await conn.fetchrow(
            """
            SELECT id, name, type, rarity, base_hp, base_attack, base_defense, base_stamina, image_credit_id
            FROM pokemon_catalog
            WHERE rarity = ANY($1::text[])
            ORDER BY random()
            LIMIT 1
            """,
            list(rarities),
        )
        if not row:
            raise ShopError(f"No pokemon found for rarity pool {rarities}")
        return row


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"{name} is required when DATABASE_URL is not set")
    return value


def _calculate_bonus_amount(last_claim_at: datetime, now: datetime) -> int:
    elapsed_seconds = max(0.0, (now - _normalize_timestamp(last_claim_at)).total_seconds())
    capped_seconds = min(elapsed_seconds, SHOP_BONUS_CAP_SECONDS)
    return int(capped_seconds * SHOP_BONUS_RATE_PER_HOUR / 3600)


def _bonus_remaining_seconds(last_claim_at: datetime, now: datetime) -> int:
    elapsed_seconds = max(0.0, (now - _normalize_timestamp(last_claim_at)).total_seconds())
    if elapsed_seconds >= SHOP_BONUS_CLAIM_INTERVAL_SECONDS:
        return 0
    return int(SHOP_BONUS_CLAIM_INTERVAL_SECONDS - elapsed_seconds)


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _resolve_roll_rarity(epic_counter: int, legendary_counter: int) -> str:
    if legendary_counter >= LEGENDARY_PITY_THRESHOLD - 1:
        return "Legendary"
    if epic_counter >= EPIC_PITY_THRESHOLD - 1:
        guaranteed_pool = {"Legendary": RARITY_PROBABILITIES["Legendary"], "Epic": RARITY_PROBABILITIES["Epic"]}
        return _weighted_rarity_choice(guaranteed_pool)
    return _weighted_rarity_choice(RARITY_PROBABILITIES)


def _weighted_rarity_choice(weights: dict[str, float]) -> str:
    roll = random.uniform(0, sum(weights.values()))
    cumulative = 0.0
    for rarity in RARITY_ORDER:
        if rarity not in weights:
            continue
        cumulative += weights[rarity]
        if roll <= cumulative:
            return rarity
    return next(reversed(weights))


def _rarity_pool_for_target(target_rarity: str) -> Sequence[str]:
    if target_rarity == "Legendary":
        return ("Legendary",)
    if target_rarity == "Epic":
        return ("Legendary", "Epic")
    if target_rarity == "Rare":
        return ("Rare",)
    return ("Common",)


def _update_pity_counters(result_rarity: str, epic_counter: int, legendary_counter: int) -> tuple[int, int]:
    if result_rarity == "Epic":
        return 0, legendary_counter + 1
    if result_rarity == "Legendary":
        return epic_counter + 1, 0
    return epic_counter + 1, legendary_counter + 1
