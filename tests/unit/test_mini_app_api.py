"""Focused unit tests for Mini App API helpers."""

import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("WEBHOOK_URL", "https://example.com")
os.environ.setdefault("BOT_TOKEN", "test-token")

import main


class _FakeCollectionPage:
    def __init__(self) -> None:
        self.entries = [
            SimpleNamespace(
                pokemon_id=25,
                sample_user_pokemon_id=1001,
                name="Pikachu",
                pokemon_type="Electric",
                rarity="Rare",
                quantity=1,
                base_hp=35,
                base_attack=55,
                base_defense=40,
                base_stamina=90,
                image_credit_id=77,
                is_locked=False,
            )
        ]
        self.total_entries = 30
        self.current_page = 2
        self.total_pages = 3
        self.page_size = 24
        self.filter_state = main.CollectionFilterState(
            rarities=("Rare",),
            types=("Electric",),
            duplicates_only=True,
            locked_only=False,
            page=2,
        )

    def has_next(self) -> bool:
        return True

    def has_previous(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_build_mini_app_collection_payload_with_filters_shapes_response(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_db = SimpleNamespace(
        get_mini_app_collection_page=AsyncMock(return_value=_FakeCollectionPage()),
        get_image_credit=AsyncMock(
            return_value=SimpleNamespace(
                storage_bucket="pokemon-assets",
                object_key="pikachu/main.png",
            )
        ),
    )
    monkeypatch.setattr(main, "DB_ENABLED", True)
    monkeypatch.setattr(main, "db", fake_db)
    monkeypatch.setenv("S3_PUBLIC_BASE_URL", "https://app.pokemoncollection.ru/storage")

    payload = await main._build_mini_app_collection_payload_with_filters(
        1640978922,
        "termenater",
        filter_state=main.CollectionFilterState(
            rarities=("Rare",),
            types=("Electric",),
            duplicates_only=True,
            locked_only=False,
            page=2,
        ),
        page_size=24,
    )

    assert payload["pageInfo"]["currentPage"] == 2
    assert payload["pageInfo"]["hasNext"] is True
    assert payload["appliedFilters"] == {
        "rarities": ["Rare"],
        "types": ["Electric"],
        "duplicatesOnly": True,
        "lockedOnly": False,
    }
    assert payload["entries"][0]["name"] == "Pikachu"
    assert payload["entries"][0]["imageUrl"] == "https://app.pokemoncollection.ru/storage/pokemon-assets/pikachu/main.png"


@pytest.mark.asyncio
async def test_build_mini_app_profile_payload_contains_profile_summary_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_db = SimpleNamespace(
        get_profile_summary=AsyncMock(
            return_value=SimpleNamespace(
                user_id=7,
                telegram_id=1640978922,
                nickname="Artem",
                tg_username="termenater",
                language="ru",
                total_unique_owned=164,
                total_unique_percent=16,
                total_catalog=1025,
                created_at=datetime.now(UTC) - timedelta(days=40),
                cover_pokemon_name="Cloyster",
                rarity_progress=[
                    SimpleNamespace(rarity="Legendary", owned_unique=14, total_catalog=65, percent=21),
                    SimpleNamespace(rarity="Epic", owned_unique=16, total_catalog=154, percent=10),
                ],
            )
        ),
        get_shop_view=AsyncMock(return_value=SimpleNamespace(balance=1250)),
    )
    monkeypatch.setattr(main, "DB_ENABLED", True)
    monkeypatch.setattr(main, "db", fake_db)

    payload = await main._build_mini_app_profile_payload(1640978922, "termenater")

    assert payload["telegramId"] == 1640978922
    assert payload["name"] == "Artem"
    assert payload["username"] == "termenater"
    assert payload["pokemonCount"] == 164
    assert payload["coins"] == 1250
    assert payload["totalCatalog"] == 1025
    assert payload["coverPokemonName"] == "Cloyster"
    assert payload["accountAgeLabel"]
    assert payload["rarityProgress"][0]["rarity"] == "Legendary"


@pytest.mark.asyncio
async def test_build_mini_app_market_listing_detail_payload_uses_active_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_db = SimpleNamespace(
        get_market_listing_summary=AsyncMock(
            return_value=SimpleNamespace(
                listing_id=10,
                user_pokemon_id=501,
                pokemon_id=91,
                name="Cloyster",
                rarity="Epic",
                pokemon_type="Water/Ice",
                price=900,
                seller_label="@seller",
                days_remaining=5,
            )
        ),
        get_pokemon_catalog_entry_by_id=AsyncMock(
            return_value=SimpleNamespace(
                pokemon_id=91,
                image_credit_id=12,
                base_hp=50,
                base_attack=95,
                base_defense=180,
                base_stamina=70,
            )
        ),
        get_pokemon_image_selection=AsyncMock(
            return_value=SimpleNamespace(
                image_credit_id=88,
                source_url="https://example.com/cloyster-alt",
                position=2,
                total=4,
            )
        ),
        get_image_credit=AsyncMock(
            return_value=SimpleNamespace(
                storage_bucket="pokemon-assets",
                object_key="cloyster/alt.png",
            )
        ),
    )
    monkeypatch.setattr(main, "DB_ENABLED", True)
    monkeypatch.setattr(main, "db", fake_db)
    monkeypatch.setenv("S3_PUBLIC_BASE_URL", "https://app.pokemoncollection.ru/storage")

    payload = await main._build_mini_app_market_listing_detail_payload(
        1640978922,
        "termenater",
        listing_id=10,
    )

    assert payload["listingId"] == 10
    assert payload["pokemonId"] == 91
    assert payload["price"] == 900
    assert payload["sellerLabel"] == "@seller"
    assert payload["imageCreditId"] == 88
    assert payload["imageVariant"] == {"position": 2, "total": 4, "canSwitch": True}
    assert payload["sourceUrl"] == "https://example.com/cloyster-alt"
    assert payload["imageUrl"] == "https://app.pokemoncollection.ru/storage/pokemon-assets/cloyster/alt.png"


@pytest.mark.asyncio
async def test_mini_app_pokemon_lock_toggle_returns_refreshed_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_db = SimpleNamespace(toggle_user_pokemon_lock=AsyncMock(return_value=None))
    monkeypatch.setattr(main, "db", fake_db)
    monkeypatch.setattr(main, "_resolve_mini_app_identity", lambda **_: (1640978922, "termenater"))
    monkeypatch.setattr(
        main,
        "_build_mini_app_pokemon_detail_payload",
        AsyncMock(return_value={"userPokemonId": 42, "isLocked": True}),
    )

    payload = await main.mini_app_pokemon_lock_toggle(
        42,
        x_telegram_init_data="init-data",
        x_dev_telegram_id=None,
    )

    fake_db.toggle_user_pokemon_lock.assert_awaited_once_with(
        1640978922,
        "termenater",
        user_pokemon_id=42,
    )
    assert payload == {"userPokemonId": 42, "isLocked": True}
