"""Unit tests for market foundation helpers."""

from datetime import UTC, datetime, timedelta

from bot.db.database import (
    MARKET_SORT_CHEAPEST,
    MARKET_SORT_NEWEST,
    MarketBrowseState,
    _calculate_market_daily_commission,
    _market_due_commission_cycles,
    _market_days_remaining,
    _market_sort_sql,
    _pokemon_release_reward,
)
from bot.handlers.sections.market import (
    _build_market_buy_keyboard,
    MARKET_CARD_ACTION_REQUEST,
    MARKET_CARD_ACTION_SELL,
    MARKET_PENDING_ACTION_BUY_PRICE,
    MARKET_PENDING_ACTION_SELL_PRICE,
    MARKET_ROUTE_MY_LISTINGS,
    MARKET_ROUTE_MY_REQUESTS,
    MARKET_ROUTE_ROOT,
    MARKET_ROUTE_SECTIONS,
    resolve_market_card_action,
)
from bot.db.database import MarketBrowsePage


def test_market_browse_state_roundtrip_preserves_filters() -> None:
    state = MarketBrowseState(
        rarities=("Legendary", "Epic"),
        affordable_only=True,
        sort_mode=MARKET_SORT_CHEAPEST,
        page=3,
    )
    restored = MarketBrowseState.from_payload(state.to_session_payload())
    assert restored == state


def test_market_browse_state_rejects_unknown_sort_mode() -> None:
    restored = MarketBrowseState.from_payload({"sort_mode": "broken"})
    assert restored.sort_mode == MARKET_SORT_NEWEST


def test_market_daily_commission_has_minimum_one() -> None:
    assert _calculate_market_daily_commission(1) == 1
    assert _calculate_market_daily_commission(99) == 1
    assert _calculate_market_daily_commission(2500) == 25


def test_pokemon_release_reward_depends_on_rarity() -> None:
    assert _pokemon_release_reward("Common") == 32
    assert _pokemon_release_reward("Rare") == 100
    assert _pokemon_release_reward("Epic") == 325
    assert _pokemon_release_reward("Legendary") == 1000


def test_market_days_remaining_rounds_up_positive_partial_day() -> None:
    expires_at = datetime.now(UTC) + timedelta(hours=3)
    assert _market_days_remaining(expires_at) == 1


def test_market_due_commission_cycles_counts_overdue_days() -> None:
    now = datetime(2026, 3, 21, 12, 0, tzinfo=UTC)
    assert _market_due_commission_cycles(
        next_commission_at=now - timedelta(days=2, hours=1),
        expires_at=now + timedelta(days=3),
        now=now,
    ) == 3


def test_market_due_commission_cycles_stops_at_expiry() -> None:
    now = datetime(2026, 3, 21, 12, 0, tzinfo=UTC)
    assert _market_due_commission_cycles(
        next_commission_at=now - timedelta(days=2),
        expires_at=now - timedelta(days=1, hours=12),
        now=now,
    ) == 1


def test_market_sort_sql_supports_newest_and_cheapest() -> None:
    assert "listed_at" in _market_sort_sql(MARKET_SORT_NEWEST)
    assert "price ASC" in _market_sort_sql(MARKET_SORT_CHEAPEST)


def test_market_card_action_branches_by_ownership() -> None:
    assert resolve_market_card_action(True) == MARKET_CARD_ACTION_SELL
    assert resolve_market_card_action(False) == MARKET_CARD_ACTION_REQUEST


def test_market_route_constants_cover_root_and_management_screens() -> None:
    assert MARKET_ROUTE_ROOT in MARKET_ROUTE_SECTIONS
    assert MARKET_ROUTE_MY_LISTINGS in MARKET_ROUTE_SECTIONS
    assert MARKET_ROUTE_MY_REQUESTS in MARKET_ROUTE_SECTIONS


def test_market_pending_input_actions_are_distinct() -> None:
    assert MARKET_PENDING_ACTION_SELL_PRICE != MARKET_PENDING_ACTION_BUY_PRICE


def test_market_buy_keyboard_matches_collection_toggle_style() -> None:
    page = MarketBrowsePage(
        entries=[],
        filter_state=MarketBrowseState(rarities=("Epic",), affordable_only=True, sort_mode=MARKET_SORT_NEWEST, page=1),
        total_entries=0,
        current_page=1,
        total_pages=1,
        current_balance=500,
    )
    keyboard = _build_market_buy_keyboard("session-1", page)
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert any(label.startswith("✅ 🟣 Epic") for label in labels)
    assert any(label.startswith("✅ 🪙 Только хватает") for label in labels)
    assert not any("⬜️" in label for label in labels)
