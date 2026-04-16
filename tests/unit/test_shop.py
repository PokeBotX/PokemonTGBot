"""Unit tests for shop helpers and state transitions."""

from datetime import UTC, datetime, timedelta

from bot.db.database import (
    SHOP_BONUS_CAP,
    SHOP_BONUS_CLAIM_INTERVAL_SECONDS,
    EPIC_PITY_THRESHOLD,
    LEGENDARY_PITY_THRESHOLD,
    _bonus_remaining_seconds,
    _calculate_bonus_amount,
    _update_pity_counters,
)
from bot.db.database import ShopView
from bot.handlers.sections.shop import (
    SHOP_VIEW_ITEMS,
    SHOP_VIEW_MAIN,
    SHOP_VIEW_POKEMON,
    _build_shop_keyboard,
    _render_shop_text,
)


def test_calculate_bonus_amount_caps_at_750() -> None:
    now = datetime.now(UTC)
    last_claim_at = now - timedelta(hours=12)
    assert _calculate_bonus_amount(last_claim_at, now) == SHOP_BONUS_CAP


def test_bonus_remaining_seconds_before_one_hour() -> None:
    now = datetime.now(UTC)
    last_claim_at = now - timedelta(minutes=10)
    assert _bonus_remaining_seconds(last_claim_at, now) == SHOP_BONUS_CLAIM_INTERVAL_SECONDS - 600


def test_bonus_remaining_seconds_zero_when_ready() -> None:
    now = datetime.now(UTC)
    last_claim_at = now - timedelta(hours=2)
    assert _bonus_remaining_seconds(last_claim_at, now) == 0


def test_epic_pity_resets_only_on_epic() -> None:
    assert _update_pity_counters("Epic", 14, 3) == (0, 4)
    assert _update_pity_counters("Legendary", 14, 39) == (15, 0)


def test_main_shop_keyboard_shows_category_buttons() -> None:
    keyboard = _build_shop_keyboard(
        "session-id",
        ShopView(
            user_id=1,
            balance=300,
            pokecoin_balance=0,
            ultraball_quantity=0,
            masterball_quantity=0,
            epic_pity_counter=0,
            legendary_pity_counter=0,
            bonus_available=0,
            bonus_ready_in_seconds=60,
        ),
        SHOP_VIEW_MAIN,
    )
    button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
    assert "🎮 Покемоны" in button_texts
    assert "🎁 Бонус" in button_texts
    assert "🎒 Предметы" in button_texts
    assert "⭐ VIP" not in button_texts


def test_pokemon_shop_keyboard_hides_only_x5_when_balance_is_low() -> None:
    keyboard = _build_shop_keyboard(
        "session-id",
        ShopView(
            user_id=1,
            balance=600,
            pokecoin_balance=0,
            ultraball_quantity=1,
            masterball_quantity=0,
            epic_pity_counter=EPIC_PITY_THRESHOLD - 1,
            legendary_pity_counter=LEGENDARY_PITY_THRESHOLD - 1,
            bonus_available=125,
            bonus_ready_in_seconds=0,
        ),
        SHOP_VIEW_POKEMON,
    )
    button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
    assert "🎲 Случайный персонаж: 💵500" in button_texts
    assert "🎲 Случайный персонаж x5: 💵2500" not in button_texts


def test_pokemon_shop_keyboard_shows_x5_for_sufficient_balance() -> None:
    keyboard = _build_shop_keyboard(
        "session-id",
        ShopView(
            user_id=1,
            balance=2500,
            pokecoin_balance=0,
            ultraball_quantity=1,
            masterball_quantity=0,
            epic_pity_counter=EPIC_PITY_THRESHOLD - 1,
            legendary_pity_counter=LEGENDARY_PITY_THRESHOLD - 1,
            bonus_available=125,
            bonus_ready_in_seconds=0,
        ),
        SHOP_VIEW_POKEMON,
    )
    button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
    assert "🎲 Случайный персонаж x5: 💵2500" in button_texts


def test_items_shop_keyboard_shows_both_item_buttons() -> None:
    keyboard = _build_shop_keyboard(
        "session-id",
        ShopView(
            user_id=1,
            balance=0,
            pokecoin_balance=0,
            ultraball_quantity=0,
            masterball_quantity=0,
            epic_pity_counter=0,
            legendary_pity_counter=0,
            bonus_available=0,
            bonus_ready_in_seconds=0,
        ),
        SHOP_VIEW_ITEMS,
    )
    button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
    assert "🟡 Ultraball: 💵200" in button_texts
    assert "🟣 Masterball: 💵800" in button_texts


def test_render_shop_text_includes_status_and_counters() -> None:
    text = _render_shop_text(
        ShopView(
            user_id=1,
            balance=500,
            pokecoin_balance=0,
            ultraball_quantity=2,
            masterball_quantity=3,
            epic_pity_counter=4,
            legendary_pity_counter=5,
            bonus_available=125,
            bonus_ready_in_seconds=0,
        ),
        "Статус",
        SHOP_VIEW_POKEMON,
        "@ash",
    )
    assert "@ash, выберите желаемую опцию" in text
    assert "🎲 - случайный персонаж: 💵500" in text
    assert "👛 Ваш баланс: 💵500" in text
    assert "Статус" in text


def test_items_shop_text_shows_owned_ball_counts() -> None:
    text = _render_shop_text(
        ShopView(
            user_id=1,
            balance=500,
            pokecoin_balance=0,
            ultraball_quantity=2,
            masterball_quantity=3,
            epic_pity_counter=0,
            legendary_pity_counter=0,
            bonus_available=0,
            bonus_ready_in_seconds=0,
        ),
        None,
        SHOP_VIEW_ITEMS,
        "@ash",
    )

    assert "⚪️ Обычный Pokéball: ∞" in text
    assert "🟡 Ultraball: 2" in text
    assert "🟣 Masterball: 3" in text
