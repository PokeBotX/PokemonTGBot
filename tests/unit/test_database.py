"""Unit tests for database helpers."""

from unittest.mock import AsyncMock, Mock

import pytest

from bot.db.database import (
    CHAT_ENCOUNTER_COUNTER_TTL_SECONDS,
    Database,
    POKEDOLLAR_CODE,
    WELCOME_POKEDOLLAR_AMOUNT,
)


@pytest.mark.asyncio
async def test_ensure_user_assigns_welcome_balance_once_on_insert() -> None:
    db = Database()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": 7})

    user_id = await db._ensure_user(conn, telegram_id=12345, username="ash")

    assert user_id == 7
    query, telegram_id, username, currency_code, welcome_amount, bonus_cap_seconds = conn.fetchrow.call_args.args
    assert "INSERT INTO user_balances" in query
    assert "SELECT upserted_user.id, currencies.id, $4" in query
    assert "INSERT INTO user_shop_state (user_id, bonus_last_claim_at)" in query
    assert telegram_id == 12345
    assert username == "ash"
    assert currency_code == POKEDOLLAR_CODE
    assert welcome_amount == WELCOME_POKEDOLLAR_AMOUNT
    assert bonus_cap_seconds > 0


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    def exists(self, key: str) -> bool:
        return key in self.values

    def incr(self, key: str) -> int:
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    def expire(self, key: str, ttl: int) -> None:
        self.ttls[key] = ttl


@pytest.mark.asyncio
async def test_note_chat_message_via_redis_uses_counter_and_sets_ttl() -> None:
    db = Database()
    db.redis = _FakeRedis()

    result = await db._note_chat_message_via_redis(777)

    assert result == 1
    assert db.redis.values["encounter:count:777"] == 1
    assert db.redis.ttls["encounter:count:777"] == CHAT_ENCOUNTER_COUNTER_TTL_SECONDS


class _AcquireContext:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self, conn) -> None:
        self.conn = conn

    def acquire(self):
        return _AcquireContext(self.conn)


@pytest.mark.asyncio
async def test_get_user_pokemon_entry_counts_owned_duplicates() -> None:
    db = Database()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        return_value={
            "pokemon_id": 743,
            "sample_user_pokemon_id": 1001,
            "name": "Ribombee",
            "rarity": "Epic",
            "type": "fairy",
            "quantity": 2,
            "base_hp": 60,
            "base_attack": 55,
            "base_defense": 60,
            "base_stamina": 124,
            "image_credit_id": None,
            "is_locked": False,
        }
    )
    db.pool = _FakePool(conn)

    entry = await db.get_user_pokemon_entry(1001)

    assert entry is not None
    assert entry.quantity == 2
    assert "SELECT COUNT(*)" in conn.fetchrow.call_args.args[0]


@pytest.mark.asyncio
async def test_get_user_pokemon_instances_for_species_propagates_total_quantity() -> None:
    db = Database()
    conn = Mock()
    conn.transaction = Mock(return_value=_AcquireContext(None))
    conn.fetch = AsyncMock(
        return_value=[
            {
                "pokemon_id": 743,
                "sample_user_pokemon_id": 1001,
                "name": "Ribombee",
                "rarity": "Epic",
                "type": "fairy",
                "quantity": 2,
                "base_hp": 60,
                "base_attack": 55,
                "base_defense": 60,
                "base_stamina": 124,
                "image_credit_id": None,
                "is_locked": False,
            },
            {
                "pokemon_id": 743,
                "sample_user_pokemon_id": 1002,
                "name": "Ribombee",
                "rarity": "Epic",
                "type": "fairy",
                "quantity": 2,
                "base_hp": 60,
                "base_attack": 55,
                "base_defense": 60,
                "base_stamina": 124,
                "image_credit_id": None,
                "is_locked": True,
            },
        ]
    )
    db.pool = _FakePool(conn)
    db._ensure_user = AsyncMock(return_value=77)

    entries = await db.get_user_pokemon_instances_for_species(12345, "ash", pokemon_id=743)

    assert [entry.quantity for entry in entries] == [2, 2]
    assert "COUNT(*) OVER" in conn.fetch.call_args.args[0]
