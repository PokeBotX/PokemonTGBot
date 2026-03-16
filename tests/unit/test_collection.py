"""Unit tests for collection helpers and filtering."""

from bot.db.database import (
    CollectionEntry,
    CollectionFilterState,
    CollectionPage,
    _normalize_collection_types,
    _paginate_collection_entries,
)
from bot.handlers.sections.collection import (
    COLLECTION_TYPE_OPTIONS,
    COLLECTION_VIEW_FILTERS,
    COLLECTION_VIEW_MAIN,
    _build_collection_keyboard,
    _format_collection_entry_line,
    _render_collection_text,
    _toggle_type_filter,
)


def _entry(
    pokemon_id: int,
    name: str,
    rarity: str,
    pokemon_type: str,
    quantity: int,
) -> CollectionEntry:
    return CollectionEntry(
        pokemon_id=pokemon_id,
        sample_user_pokemon_id=pokemon_id * 10,
        name=name,
        rarity=rarity,
        pokemon_type=pokemon_type,
        quantity=quantity,
        base_hp=10,
        base_attack=20,
        base_defense=30,
        base_stamina=40,
        image_credit_id=None,
    )


def test_normalize_collection_types_splits_combined_type_values() -> None:
    assert _normalize_collection_types("grass/poison") == ("grass", "poison")
    assert _normalize_collection_types("water/1") == ("water",)


def test_toggle_type_filter_never_keeps_more_than_two_types() -> None:
    state = CollectionFilterState(types=("fire", "water"))
    updated = _toggle_type_filter(state, "grass")
    assert updated.types == ("fire", "water")


def test_paginate_collection_entries_applies_type_and_duplicates_filters() -> None:
    entries = [
        _entry(1, "Bulbasaur", "Epic", "grass/poison", 2),
        _entry(4, "Charmander", "Epic", "fire", 1),
        _entry(6, "Charizard", "Legendary", "fire/flying", 3),
    ]
    page = _paginate_collection_entries(
        entries,
        CollectionFilterState(types=("fire", "flying"), duplicates_only=True),
    )
    assert page.total_entries == 1
    assert page.entries[0].name == "Charizard"


def test_format_collection_entry_line_uses_compact_quantity_format() -> None:
    line = _format_collection_entry_line(_entry(180, "Flaaffy", "Epic", "electric", 3))
    assert "Flaaffy x3 | id: 180" in line


def test_build_collection_keyboard_shows_filter_and_detail_buttons() -> None:
    page = CollectionPage(
        entries=[_entry(index, f"Pokemon {index}", "Common", "normal", 1) for index in range(1, 5)],
        filter_state=CollectionFilterState(),
        total_entries=4,
        current_page=1,
        total_pages=1,
    )
    keyboard = _build_collection_keyboard("session-id", page, COLLECTION_VIEW_MAIN)
    button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
    assert "🔎 1" in button_texts
    assert "⚙️ Фильтры" in button_texts
    assert "🔙 Назад в меню" in button_texts


def test_build_collection_filter_keyboard_shows_type_toggles_and_reset() -> None:
    page = CollectionPage(
        entries=[],
        filter_state=CollectionFilterState(rarities=("Epic",), types=("fire",), duplicates_only=True),
        total_entries=0,
        current_page=1,
        total_pages=1,
    )
    keyboard = _build_collection_keyboard("session-id", page, COLLECTION_VIEW_FILTERS)
    button_texts = [button.text for row in keyboard.inline_keyboard for button in row]
    assert any(text.endswith("Epic") for text in button_texts)
    assert any("fire" in text for text in button_texts if text in button_texts)
    assert "🧹 Сброс" in button_texts
    assert "🔙 Назад" in button_texts


def test_render_collection_text_shows_active_filters_summary() -> None:
    page = CollectionPage(
        entries=[_entry(25, "Pikachu", "Rare", "electric", 2)],
        filter_state=CollectionFilterState(rarities=("Rare",), types=("electric",), duplicates_only=True),
        total_entries=1,
        current_page=1,
        total_pages=1,
    )
    text = _render_collection_text("@ash", page, COLLECTION_VIEW_MAIN)
    assert "@ash, ваша коллекция" in text
    assert "Активные фильтры:" in text
    assert "Rare" in text
    assert "electric" in text


def test_render_filter_screen_mentions_two_type_limit() -> None:
    page = CollectionPage(
        entries=[],
        filter_state=CollectionFilterState(types=(COLLECTION_TYPE_OPTIONS[0], COLLECTION_TYPE_OPTIONS[1])),
        total_entries=0,
        current_page=1,
        total_pages=1,
    )
    text = _render_collection_text("@ash", page, COLLECTION_VIEW_FILTERS)
    assert "Можно выбрать до 2 стихий одновременно." in text
