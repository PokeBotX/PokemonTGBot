"""Focused schema-level regression checks for hardening work."""

from pathlib import Path


SCHEMA_PATH = Path("sql/schema.sql")


def test_market_listings_no_longer_define_global_unique_instance_column() -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    assert '"pokemon_instance_id" bigint UNIQUE NOT NULL' not in schema
    assert 'CREATE UNIQUE INDEX IF NOT EXISTS market_listings_active_instance_idx' in schema


def test_schema_has_lower_username_index() -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    assert 'CREATE INDEX IF NOT EXISTS users_lower_tg_username_idx' in schema


def test_schema_drops_legacy_market_unique_constraint() -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    assert 'market_listings_pokemon_instance_id_key' in schema
    assert 'DROP CONSTRAINT "market_listings_pokemon_instance_id_key"' in schema


def test_schema_has_non_negative_and_positive_safety_checks() -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    assert 'user_balances_amount_non_negative' in schema
    assert 'user_items_quantity_non_negative' in schema
    assert 'market_listings_price_positive' in schema
    assert 'market_buy_requests_price_positive' in schema


def test_schema_uses_timestamptz_for_new_high_value_temporal_columns() -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    assert '"created_at" timestamptz NOT NULL DEFAULT (now())' in schema
    assert '"updated_at" timestamptz NOT NULL DEFAULT (now())' in schema
    assert '"obtained_at" timestamptz NOT NULL DEFAULT (now())' in schema


def test_schema_migrates_legacy_naive_timestamps_and_removes_legacy_market_columns() -> None:
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    assert 'ALTER COLUMN "created_at" TYPE timestamptz' in schema
    assert 'ALTER COLUMN "updated_at" TYPE timestamptz' in schema
    assert 'ALTER COLUMN "obtained_at" TYPE timestamptz' in schema
    assert 'DROP COLUMN "start_date"' in schema
    assert 'DROP COLUMN "end_date"' in schema
    assert 'DROP COLUMN "purchaser_user_id"' in schema
    assert 'market_listings_purchaser_user_id_fkey' not in schema
