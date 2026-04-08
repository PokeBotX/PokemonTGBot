"""Unit tests for trade helpers and schema wiring."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from bot.db.database import (
    TRADE_ACTIVE_TTL_SECONDS,
    TRADE_MAX_OFFERS_PER_SIDE,
    TRADE_PENDING_TTL_SECONDS,
)
from bot.handlers.sections.trade import _seconds_remaining


def test_trade_timeouts_and_limits_are_locked() -> None:
    assert TRADE_PENDING_TTL_SECONDS == 120
    assert TRADE_ACTIVE_TTL_SECONDS == 600
    assert TRADE_MAX_OFFERS_PER_SIDE == 6


def test_trade_schema_tables_and_links_exist() -> None:
    schema = Path("sql/schema.sql").read_text(encoding="utf-8")
    assert 'CREATE TABLE IF NOT EXISTS "trade_sessions"' in schema
    assert 'CREATE TABLE IF NOT EXISTS "trade_user_links"' in schema
    assert 'CREATE TABLE IF NOT EXISTS "trade_offer_items"' in schema
    assert 'trade_sessions_not_self_trade' in schema


def test_trade_seconds_remaining_counts_future_time() -> None:
    expires_at = datetime.now(UTC) + timedelta(seconds=15)
    assert 1 <= _seconds_remaining(expires_at) <= 15


def test_trade_seconds_remaining_clamps_past_time_to_zero() -> None:
    expires_at = datetime.now(UTC) - timedelta(seconds=3)
    assert _seconds_remaining(expires_at) == 0
