"""Small helpers for safe HTML rendering in Telegram messages."""

from __future__ import annotations

from html import escape
from typing import Optional


def escape_html(value: object) -> str:
    """Escape arbitrary values for Telegram HTML parse mode."""
    return escape("" if value is None else str(value), quote=False)


def display_name(username: Optional[str], first_name: Optional[str], fallback: str = "тренер") -> str:
    """Build a human-friendly user label without forcing a broken @prefix."""
    if username:
        return f"@{username}"
    if first_name:
        return first_name
    return fallback
