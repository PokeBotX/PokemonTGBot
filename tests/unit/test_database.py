"""Unit tests for database helpers."""

from unittest.mock import AsyncMock

import pytest

from bot.db.database import Database, POKEDOLLAR_CODE, WELCOME_POKEDOLLAR_AMOUNT


@pytest.mark.asyncio
async def test_ensure_user_assigns_welcome_balance_once_on_insert() -> None:
    db = Database()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": 7})

    user_id = await db._ensure_user(conn, telegram_id=12345, username="ash")

    assert user_id == 7
    query, telegram_id, username, currency_code, welcome_amount = conn.fetchrow.call_args.args
    assert "INSERT INTO user_balances" in query
    assert "SELECT upserted_user.id, currencies.id, $4" in query
    assert telegram_id == 12345
    assert username == "ash"
    assert currency_code == POKEDOLLAR_CODE
    assert welcome_amount == WELCOME_POKEDOLLAR_AMOUNT
