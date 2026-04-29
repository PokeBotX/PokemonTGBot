"""Unit tests for profile helpers."""

from datetime import UTC, datetime, timedelta

from bot.db.database import ProfileRarityProgress, ProfileReferral, ProfileSummary, _calculate_percent
from pathlib import Path

from bot.handlers.sections.profile import (
    _display_self_profile_owner,
    _find_local_pokemon_image,
    _humanize_account_age,
    _render_profile_text,
    _render_referral_text,
    _resolve_profile_image_path,
)
from unittest.mock import Mock
from telegram import Update, User


def _summary(created_at: datetime) -> ProfileSummary:
    return ProfileSummary(
        user_id=1,
        telegram_id=1640978922,
        tg_username="artyom",
        nickname="Артём Марьинский",
        language="ru",
        created_at=created_at,
        total_unique_owned=128,
        total_catalog=1025,
        total_unique_percent=12,
        rarity_progress=(
            ProfileRarityProgress("Legendary", 2, 76, 3),
            ProfileRarityProgress("Epic", 14, 245, 6),
            ProfileRarityProgress("Rare", 39, 317, 12),
            ProfileRarityProgress("Common", 73, 387, 19),
        ),
        profile_pic_credit_id=None,
        cover_pokemon_name=None,
        total_form_owned=131,
        total_form_catalog=1080,
        total_form_percent=12,
    )


def test_calculate_percent_rounds_down_for_profile_progress() -> None:
    assert _calculate_percent(128, 1025) == 12
    assert _calculate_percent(0, 1025) == 0


def test_humanize_account_age_uses_days_for_recent_accounts() -> None:
    created_at = datetime.now(UTC) - timedelta(days=3)
    assert _humanize_account_age(created_at) == "3 дня"


def test_humanize_account_age_uses_months_for_mid_age_accounts() -> None:
    created_at = datetime.now(UTC) - timedelta(days=65)
    assert _humanize_account_age(created_at) == "2 месяца"


def test_render_profile_text_includes_total_and_rarity_progress() -> None:
    text = _render_profile_text(_summary(datetime.now(UTC) - timedelta(days=40)), "Артём")
    assert "ваш профиль" in text
    assert "Базовый покедекс" in text
    assert "Все формы" in text
    assert "128" in text
    assert "131" in text
    assert "1025" in text
    assert "1080" in text
    assert "Legendary" in text
    assert "Epic" in text
    assert "Возраст аккаунта" in text


def test_render_referral_text_uses_ready_referral_link() -> None:
    text = _render_referral_text(
        "Артём",
        ProfileReferral(
            referral_code="ref_1640978922",
            referral_link="https://t.me/testbot?start=ref_1640978922",
        ),
    )
    assert "ваша реферальная ссылка" in text
    assert "https://t.me/testbot?start=ref_1640978922" in text


def test_display_profile_owner_prefers_nickname_then_username() -> None:
    from bot.handlers.sections.profile import _display_profile_owner

    assert _display_profile_owner(_summary(datetime.now(UTC))) == "Артём Марьинский"


def test_display_self_profile_owner_prefers_current_user_first_name_when_no_nickname() -> None:
    summary = ProfileSummary(
        user_id=1,
        telegram_id=1640978922,
        tg_username="artyom",
        nickname=None,
        language="ru",
        created_at=datetime.now(UTC),
        total_unique_owned=0,
        total_catalog=1025,
        total_unique_percent=0,
        rarity_progress=(),
        profile_pic_credit_id=None,
        cover_pokemon_name=None,
    )
    user = Mock(spec=User)
    user.first_name = "Артём"
    user.username = "artyom"
    update = Mock(spec=Update)
    update.effective_user = user

    assert _display_self_profile_owner(update, summary) == "Артём"


def test_find_local_pokemon_image_returns_first_known_asset() -> None:
    image_path = _find_local_pokemon_image("Bulbasaur")
    assert image_path is not None
    assert image_path.name == "Pasted image.png"


def test_resolve_profile_image_path_falls_back_to_default_image() -> None:
    summary = _summary(datetime.now(UTC))
    resolved = _resolve_profile_image_path(summary)
    assert resolved == Path("image_profile.png")
