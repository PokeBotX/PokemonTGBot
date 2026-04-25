"""Pending-action primitives for the admin bot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Optional

ADMIN_PENDING_ACTION_TTL_SECONDS = 10 * 60


@dataclass(slots=True)
class AdminPendingAction:
    """A staged privileged mutation waiting for superadmin confirmation."""

    action_type: str
    title: str
    description: str
    input_payload: dict[str, object] = field(default_factory=dict)
    target_username: Optional[str] = None
    target_telegram_id: Optional[int] = None
    target_user_id: Optional[int] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_expired(self) -> bool:
        """Return True when the confirmation window has elapsed."""
        return datetime.now(UTC) > self.created_at + timedelta(seconds=ADMIN_PENDING_ACTION_TTL_SECONDS)

    def to_session_payload(self) -> dict[str, object]:
        """Serialize pending action into session-safe payload."""
        return {
            "action_type": self.action_type,
            "title": self.title,
            "description": self.description,
            "input_payload": self.input_payload,
            "target_username": self.target_username,
            "target_telegram_id": self.target_telegram_id,
            "target_user_id": self.target_user_id,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_session_payload(cls, payload: Optional[dict[str, object]]) -> Optional["AdminPendingAction"]:
        """Deserialize pending action payload from session data."""
        if not payload:
            return None
        created_at_raw = payload.get("created_at")
        created_at = datetime.fromisoformat(created_at_raw) if isinstance(created_at_raw, str) else datetime.now(UTC)
        return cls(
            action_type=str(payload["action_type"]),
            title=str(payload["title"]),
            description=str(payload["description"]),
            input_payload=dict(payload.get("input_payload") or {}),
            target_username=payload.get("target_username") if isinstance(payload.get("target_username"), str) else None,
            target_telegram_id=int(payload["target_telegram_id"]) if payload.get("target_telegram_id") is not None else None,
            target_user_id=int(payload["target_user_id"]) if payload.get("target_user_id") is not None else None,
            created_at=created_at,
        )
