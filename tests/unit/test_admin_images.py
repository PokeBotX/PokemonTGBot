"""Unit tests for admin-bot image helpers and validation."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from telegram import Document, Message, PhotoSize

from bot.admin.handlers import _normalize_yes_no, _resolve_admin_upload_media
from bot.admin.storage import build_admin_object_key
from bot.db.database import ShopError


def test_build_admin_object_key_slugifies_inputs() -> None:
    key = build_admin_object_key(
        pokemon_id=91,
        pokemon_name="Mr. Mime",
        file_unique_id="AbC 123",
        file_name="Art.PNG",
    )

    assert key == "pokemon/91/mr.-mime-abc-123.png"


def test_normalize_yes_no_accepts_common_variants() -> None:
    assert _normalize_yes_no("да") is True
    assert _normalize_yes_no("YES") is True
    assert _normalize_yes_no("нет") is False
    assert _normalize_yes_no("0") is False


def test_normalize_yes_no_rejects_unknown_value() -> None:
    with pytest.raises(ShopError, match="Отправьте 'да' или 'нет'"):
        _normalize_yes_no("maybe")


def test_resolve_admin_upload_media_prefers_largest_photo() -> None:
    message = Mock(spec=Message)
    small = Mock(spec=PhotoSize)
    small.file_id = "photo-small"
    small.file_unique_id = "small"
    large = Mock(spec=PhotoSize)
    large.file_id = "photo-large"
    large.file_unique_id = "large"
    message.photo = [small, large]
    message.document = None

    file_id, unique_id, file_name, content_type = _resolve_admin_upload_media(message)

    assert file_id == "photo-large"
    assert unique_id == "large"
    assert file_name == "large.jpg"
    assert content_type == "image/jpeg"


def test_resolve_admin_upload_media_accepts_image_document() -> None:
    message = Mock(spec=Message)
    message.photo = []
    document = Mock(spec=Document)
    document.file_id = "doc-1"
    document.file_unique_id = "uniq-1"
    document.file_name = "cloyster.webp"
    document.mime_type = "image/webp"
    message.document = document

    file_id, unique_id, file_name, content_type = _resolve_admin_upload_media(message)

    assert file_id == "doc-1"
    assert unique_id == "uniq-1"
    assert file_name == "cloyster.webp"
    assert content_type == "image/webp"


def test_resolve_admin_upload_media_rejects_non_image_document() -> None:
    message = Mock(spec=Message)
    message.photo = []
    document = Mock(spec=Document)
    document.mime_type = "application/pdf"
    message.document = document

    with pytest.raises(ShopError, match="Document должен быть изображением"):
        _resolve_admin_upload_media(message)
