"""Unit tests for database helpers."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from bot.db.database import (
    CHAT_ENCOUNTER_COUNTER_TTL_SECONDS,
    Database,
    FORM_KIND_BASE,
    FORM_KIND_GIGANTAMAX,
    FORM_KIND_MEGA,
    FORM_KIND_SHINY,
    PVP_TEAM_SLOT_COUNT,
    POKEDOLLAR_CODE,
    ShopError,
    WELCOME_POKEDOLLAR_AMOUNT,
    _build_base_dex_form_code,
    _dex_form_sort_sql,
    _choose_form_overlay_kind,
    _form_badge_from_dex_form_code,
    _form_kind_from_dex_form_code,
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
            "dex_form_code": "743-0",
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
    assert entry.dex_form_code == "743-0"
    assert entry.form_badge == "Shiny"
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
                "dex_form_code": "743",
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
                "dex_form_code": "743-1",
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
    assert [entry.form_badge for entry in entries] == [None, "Mega"]
    assert "COUNT(*) OVER" in conn.fetch.call_args.args[0]


@pytest.mark.asyncio
async def test_search_pokemon_catalog_returns_all_matching_forms_with_badges() -> None:
    db = Database()
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {
                "pokemon_id": 133,
                "dex_form_code": "133",
                "name": "Eevee",
                "rarity": "Common",
                "type": "Normal",
                "base_hp": 55,
                "base_attack": 55,
                "base_defense": 50,
                "base_stamina": 55,
                "image_credit_id": None,
            },
            {
                "pokemon_id": 10133,
                "dex_form_code": "133-0",
                "name": "Eevee",
                "rarity": "Epic",
                "type": "Normal",
                "base_hp": 55,
                "base_attack": 55,
                "base_defense": 50,
                "base_stamina": 55,
                "image_credit_id": None,
            },
            {
                "pokemon_id": 10134,
                "dex_form_code": "133-1",
                "name": "Eevee",
                "rarity": "Legendary",
                "type": "Normal",
                "base_hp": 65,
                "base_attack": 65,
                "base_defense": 60,
                "base_stamina": 65,
                "image_credit_id": None,
            },
        ]
    )
    db.pool = _FakePool(conn)

    results = await db.search_pokemon_catalog("Eevee", limit=10)

    assert [entry.dex_form_code for entry in results] == ["133", "133-0", "133-1"]
    assert [entry.form_badge for entry in results] == [None, "Shiny", "Mega"]
    query = conn.fetch.call_args.args[0]
    assert "split_part(COALESCE(dex_form_code, ''), '-', 1)::int ASC" in query


@pytest.mark.asyncio
async def test_get_pokemon_catalog_entries_by_display_id_returns_all_matching_forms() -> None:
    db = Database()
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {
                "pokemon_id": 197,
                "dex_form_code": "197",
                "name": "Umbreon",
                "rarity": "Epic",
                "type": "Dark",
                "base_hp": 95,
                "base_attack": 65,
                "base_defense": 110,
                "base_stamina": 130,
                "image_credit_id": None,
            },
            {
                "pokemon_id": 10197,
                "dex_form_code": "197-0",
                "name": "Umbreon",
                "rarity": "Legendary",
                "type": "Dark",
                "base_hp": 95,
                "base_attack": 65,
                "base_defense": 110,
                "base_stamina": 130,
                "image_credit_id": None,
            },
        ]
    )
    db.pool = _FakePool(conn)

    results = await db.get_pokemon_catalog_entries_by_display_id("197")

    assert [entry.dex_form_code for entry in results] == ["197", "197-0"]
    assert [entry.form_badge for entry in results] == [None, "Shiny"]
    query = conn.fetch.call_args.args[0]
    assert "split_part(COALESCE(dex_form_code, id::text), '-', 1) = $1" in query


@pytest.mark.asyncio
async def test_profile_rarity_progress_counts_base_forms_only() -> None:
    db = Database()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(
        return_value={
            "user_id": 1,
            "tg_user_id": 12345,
            "tg_username": "ash",
            "nickname": "Ash",
            "created_at": datetime(2026, 4, 1, tzinfo=UTC),
            "language": "ru",
            "profile_pic_credit_id": None,
            "cover_pokemon_name": None,
            "total_unique_owned": 10,
            "total_catalog": 1025,
            "total_form_owned": 13,
            "total_form_catalog": 1100,
        }
    )
    conn.fetch = AsyncMock(
        return_value=[
            {"rarity": "Legendary", "total_catalog": 65, "owned_unique": 14},
            {"rarity": "Epic", "total_catalog": 154, "owned_unique": 16},
            {"rarity": "Rare", "total_catalog": 306, "owned_unique": 40},
            {"rarity": "Common", "total_catalog": 514, "owned_unique": 94},
        ]
    )

    summary = await db._fetch_profile_summary_by_user_id(conn, 1)

    assert summary.rarity_progress[0].owned_unique == 14
    assert summary.rarity_progress[0].total_catalog == 65
    rarity_query = conn.fetch.call_args.args[0]
    assert "COUNT(DISTINCT split_part(COALESCE(pc.dex_form_code, pc.id::text), '-', 1))::int AS total_catalog" in rarity_query
    assert "COUNT(DISTINCT split_part(COALESCE(owned_pc.dex_form_code, owned_pc.id::text), '-', 1))::int AS owned_unique" in rarity_query


def test_dex_form_sort_sql_orders_base_before_form_suffixes() -> None:
    sql = _dex_form_sort_sql(qualified_column="pc.dex_form_code")

    assert "split_part(COALESCE(pc.dex_form_code, ''), '-', 1)::int ASC" in sql
    assert "WHEN position('-' in COALESCE(pc.dex_form_code, '')) = 0 THEN -1" in sql
    assert "ELSE split_part(COALESCE(pc.dex_form_code, ''), '-', 2)::int" in sql


@pytest.mark.asyncio
async def test_collection_page_orders_entries_by_dex_form_code_instead_of_internal_id() -> None:
    db = Database()
    conn = AsyncMock()
    conn.transaction = Mock(return_value=_AcquireContext(None))
    conn.fetchval = AsyncMock(side_effect=[3, 3])
    conn.fetch = AsyncMock(return_value=[])
    db.pool = _FakePool(conn)
    db._ensure_user = AsyncMock(return_value=77)

    await db.get_mini_app_collection_page(12345, "ash", page_size=24)

    query = conn.fetch.call_args.args[0]
    assert "ORDER BY split_part(COALESCE(pc.dex_form_code, ''), '-', 1)::int ASC" in query
    assert "WHEN position('-' in COALESCE(pc.dex_form_code, '')) = 0 THEN -1" in query


@pytest.mark.asyncio
async def test_resolve_pokemon_image_selection_uses_saved_variant_when_valid() -> None:
    db = Database()
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {
                "image_credit_id": 55,
                "display_order": 1,
                "is_default": True,
                "source": "https://example.com/default",
            },
            {
                "image_credit_id": 77,
                "display_order": 2,
                "is_default": False,
                "source": "https://example.com/alt",
            },
        ]
    )
    conn.fetchrow = AsyncMock(return_value={"image_credit_id": 77})
    conn.execute = AsyncMock()

    selection = await db._resolve_pokemon_image_selection_for_user_id(conn, user_id=1, pokemon_id=25)

    assert selection.image_credit_id == 77
    assert selection.source_url == "https://example.com/alt"
    assert selection.position == 2
    assert selection.total == 2
    conn.execute.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_pokemon_image_selection_repairs_invalid_saved_variant() -> None:
    db = Database()
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {
                "image_credit_id": 55,
                "display_order": 1,
                "is_default": True,
                "source": "https://example.com/default",
            },
            {
                "image_credit_id": 77,
                "display_order": 2,
                "is_default": False,
                "source": "https://example.com/alt",
            },
        ]
    )
    conn.fetchrow = AsyncMock(return_value={"image_credit_id": 999})
    conn.execute = AsyncMock()

    selection = await db._resolve_pokemon_image_selection_for_user_id(conn, user_id=1, pokemon_id=25)

    assert selection.image_credit_id == 55
    assert selection.position == 1
    conn.execute.assert_awaited()
    assert "DELETE FROM user_pokemon_image_preferences" in conn.execute.call_args.args[0]


@pytest.mark.asyncio
async def test_cycle_pokemon_image_selection_persists_next_variant() -> None:
    db = Database()
    conn = AsyncMock()
    conn.transaction = Mock(return_value=_AcquireContext(None))
    conn.fetch = AsyncMock(
        return_value=[
            {
                "image_credit_id": 55,
                "display_order": 1,
                "is_default": True,
                "source": "https://example.com/default",
            },
            {
                "image_credit_id": 77,
                "display_order": 2,
                "is_default": False,
                "source": "https://example.com/alt",
            },
        ]
    )
    conn.fetchrow = AsyncMock(return_value={"image_credit_id": 55})
    conn.execute = AsyncMock()
    db.pool = _FakePool(conn)
    db._ensure_user = AsyncMock(return_value=7)

    selection = await db.cycle_pokemon_image_selection(12345, "ash", pokemon_id=25)

    assert selection.image_credit_id == 77
    assert selection.position == 2
    assert "INSERT INTO user_pokemon_image_preferences" in conn.execute.call_args.args[0]


@pytest.mark.asyncio
async def test_ensure_catalog_image_variant_materialized_inserts_legacy_default_when_missing() -> None:
    db = Database()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"image_credit_id": 55})
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()

    await db._ensure_catalog_image_variant_materialized(conn, pokemon_id=25)

    insert_query, pokemon_id, image_credit_id, display_order, is_default = conn.execute.call_args.args
    assert "INSERT INTO pokemon_image_variants" in insert_query
    assert pokemon_id == 25
    assert image_credit_id == 55
    assert display_order == 1
    assert is_default is True


@pytest.mark.asyncio
async def test_ensure_catalog_image_variant_materialized_uses_next_order_when_variants_exist() -> None:
    db = Database()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"image_credit_id": 55})
    conn.fetchval = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(
        return_value=[
            {
                "image_credit_id": 77,
                "display_order": 1,
                "is_default": False,
            }
        ]
    )
    conn.execute = AsyncMock()

    await db._ensure_catalog_image_variant_materialized(conn, pokemon_id=25)

    insert_query, pokemon_id, image_credit_id, display_order, is_default = conn.execute.call_args.args
    assert "INSERT INTO pokemon_image_variants" in insert_query
    assert pokemon_id == 25
    assert image_credit_id == 55
    assert display_order == 2
    assert is_default is True


def test_form_helpers_resolve_first_wave_form_codes() -> None:
    assert _build_base_dex_form_code(1) == "1"
    assert _form_kind_from_dex_form_code("1") == FORM_KIND_BASE
    assert _form_kind_from_dex_form_code("1-0") == FORM_KIND_SHINY
    assert _form_kind_from_dex_form_code("1-1") == FORM_KIND_MEGA
    assert _form_kind_from_dex_form_code("1-2") == FORM_KIND_GIGANTAMAX
    assert _form_badge_from_dex_form_code("1") is None
    assert _form_badge_from_dex_form_code("1-0") == "Shiny"
    assert _form_badge_from_dex_form_code("1-1") == "Mega"
    assert _form_badge_from_dex_form_code("1-2") == "Gigantamax"


def test_choose_form_overlay_kind_uses_first_wave_probabilities() -> None:
    assert _choose_form_overlay_kind((FORM_KIND_SHINY, FORM_KIND_MEGA, FORM_KIND_GIGANTAMAX), roll=0.0) == FORM_KIND_SHINY
    assert _choose_form_overlay_kind((FORM_KIND_SHINY, FORM_KIND_MEGA, FORM_KIND_GIGANTAMAX), roll=10.0) == FORM_KIND_MEGA
    assert _choose_form_overlay_kind((FORM_KIND_SHINY, FORM_KIND_MEGA, FORM_KIND_GIGANTAMAX), roll=15.0) == FORM_KIND_GIGANTAMAX
    assert _choose_form_overlay_kind((FORM_KIND_SHINY, FORM_KIND_MEGA, FORM_KIND_GIGANTAMAX), roll=20.0) == FORM_KIND_BASE
    assert _choose_form_overlay_kind((FORM_KIND_MEGA,), roll=3.0) == FORM_KIND_MEGA
    assert _choose_form_overlay_kind((FORM_KIND_MEGA,), roll=6.0) == FORM_KIND_BASE


@pytest.mark.asyncio
async def test_admin_create_pokemon_species_assigns_base_dex_form_code() -> None:
    db = Database()
    conn = AsyncMock()
    conn.transaction = Mock(return_value=_AcquireContext(None))
    conn.fetchval = AsyncMock(side_effect=[None, None, 25])
    db.pool = _FakePool(conn)

    created_id = await db.admin_create_pokemon_species(
        pokemon_id=25,
        name="Pikachu",
        pokemon_type="Electric",
        rarity="Rare",
        base_hp=35,
        base_attack=55,
        base_defense=40,
        base_stamina=90,
    )

    assert created_id == 25
    insert_query, pokemon_id, dex_form_code, *_ = conn.fetchval.call_args.args
    assert "INSERT INTO pokemon_catalog" in insert_query
    assert pokemon_id == 25
    assert dex_form_code == "25"


@pytest.mark.asyncio
async def test_fetch_pvp_team_returns_five_slots_with_gaps() -> None:
    db = Database()
    conn = AsyncMock()
    conn.fetch = AsyncMock(
        return_value=[
            {
                "slot_index": 1,
                "pokemon_id": 197,
                "sample_user_pokemon_id": 7001,
                "name": "Umbreon",
                "rarity": "Epic",
                "type": "Dark",
                "dex_form_code": "197",
                "quantity": 1,
                "base_hp": 95,
                "base_attack": 65,
                "base_defense": 110,
                "base_stamina": 130,
                "image_credit_id": None,
                "is_locked": False,
            },
            {
                "slot_index": 3,
                "pokemon_id": 10197,
                "sample_user_pokemon_id": 7002,
                "name": "Umbreon",
                "rarity": "Legendary",
                "type": "Dark",
                "dex_form_code": "197-0",
                "quantity": 1,
                "base_hp": 95,
                "base_attack": 65,
                "base_defense": 110,
                "base_stamina": 130,
                "image_credit_id": None,
                "is_locked": True,
            },
        ]
    )

    team = await db._fetch_pvp_team(conn, 77)

    assert len(team.slots) == PVP_TEAM_SLOT_COUNT
    assert team.filled_slots == 2
    assert team.is_complete is False
    assert team.slots[0].entry is not None
    assert team.slots[1].entry is None
    assert team.slots[2].entry is not None
    assert team.slots[2].entry.form_badge == "Shiny"


@pytest.mark.asyncio
async def test_get_market_sell_precheck_error_rejects_team_member() -> None:
    db = Database()
    conn = Mock()
    conn.transaction = Mock(return_value=_AcquireContext(None))
    conn.fetchrow = AsyncMock(
        return_value={
            "id": 55,
            "owner_user_id": 77,
            "is_locked": False,
            "released_at": None,
        }
    )
    conn.fetchval = AsyncMock(return_value=0)
    db.pool = _FakePool(conn)
    db._ensure_user = AsyncMock(return_value=77)
    db._is_user_pokemon_in_pvp_team = AsyncMock(return_value=True)

    error = await db.get_market_sell_precheck_error(12345, "ash", user_pokemon_id=55)

    assert error == "Нельзя создать лот: этот покемон состоит в боевой команде."


@pytest.mark.asyncio
async def test_add_trade_offer_pokemon_rejects_team_member() -> None:
    db = Database()
    conn = Mock()
    conn.transaction = Mock(return_value=_AcquireContext(None))
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(
        return_value={
            "owner_user_id": 77,
            "is_locked": False,
            "released_at": None,
        }
    )
    db.pool = _FakePool(conn)
    db._ensure_user = AsyncMock(return_value=77)
    db._get_user_id_by_telegram_id = AsyncMock(return_value=77)
    db._fetch_active_trade_row_for_user = AsyncMock(return_value={"id": 91})
    db._ensure_trade_mutable = AsyncMock()
    db._is_user_pokemon_in_pvp_team = AsyncMock(return_value=True)

    with pytest.raises(ShopError, match="боевой команды"):
        await db.add_trade_offer_pokemon(
            telegram_id=12345,
            username="ash",
            user_pokemon_id=55,
        )
