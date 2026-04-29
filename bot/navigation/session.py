"""Session management for menu navigation."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError

SESSION_TTL_SECONDS = 10 * 60
CALLBACK_LOCK_TTL_SECONDS = 10
PENDING_INPUT_TTL_SECONDS = 10 * 60
MAX_IN_MEMORY_SESSIONS = 2000
MAX_IN_MEMORY_CALLBACK_LOCKS = 5000
MAX_IN_MEMORY_PENDING_INPUTS = 2000
DEFAULT_SESSION_KEY_PREFIX = "menu_session:"
DEFAULT_CALLBACK_LOCK_KEY_PREFIX = "callback_lock:"
DEFAULT_PENDING_INPUT_KEY_PREFIX = "pending_input:"


@dataclass
class MenuSession:
    """Menu session data."""

    session_id: str
    chat_id: int
    message_id: int
    message_thread_id: Optional[int]
    user_id: int
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(init=False)

    def __post_init__(self) -> None:
        self.expires_at = self.created_at + timedelta(seconds=SESSION_TTL_SECONDS)

    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.now(timezone.utc) > self.expires_at

    def matches_context(
        self,
        chat_id: int,
        message_id: int,
        message_thread_id: Optional[int] = None,
    ) -> bool:
        """Check if session matches given context."""
        thread_matches = (
            self.message_thread_id == message_thread_id
            or self.message_thread_id is None
            or message_thread_id is None
        )
        return (
            self.chat_id == chat_id
            and self.message_id == message_id
            and thread_matches
        )

    def to_json(self) -> str:
        """Serialize session for Redis storage."""
        return json.dumps(
            {
                "session_id": self.session_id,
                "chat_id": self.chat_id,
                "message_id": self.message_id,
                "message_thread_id": self.message_thread_id,
                "user_id": self.user_id,
                "data": self.data,
                "created_at": self.created_at.isoformat(),
            }
        )

    @classmethod
    def from_json(cls, payload: str) -> "MenuSession":
        """Deserialize session from Redis payload."""
        data = json.loads(payload)
        session = cls(
            session_id=str(data["session_id"]),
            chat_id=int(data["chat_id"]),
            message_id=int(data["message_id"]),
            message_thread_id=data.get("message_thread_id"),
            user_id=int(data["user_id"]),
            data=data.get("data") or {},
            created_at=datetime.fromisoformat(data["created_at"]),
        )
        return session


@dataclass
class PendingInput:
    """Pending text-input action for a user."""

    action: str
    chat_id: int
    user_id: int
    source_message_id: Optional[int] = None
    source_message_thread_id: Optional[int] = None
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_expired(self) -> bool:
        """Check whether the pending input has expired."""
        return datetime.now(timezone.utc) > self.created_at + timedelta(seconds=PENDING_INPUT_TTL_SECONDS)

    def to_json(self) -> str:
        """Serialize pending input for Redis storage."""
        return json.dumps(
            {
                "action": self.action,
                "chat_id": self.chat_id,
                "user_id": self.user_id,
                "source_message_id": self.source_message_id,
                "source_message_thread_id": self.source_message_thread_id,
                "data": self.data,
                "created_at": self.created_at.isoformat(),
            }
        )

    @classmethod
    def from_json(cls, payload: str) -> "PendingInput":
        """Deserialize pending input from Redis payload."""
        data = json.loads(payload)
        return cls(
            action=str(data["action"]),
            chat_id=int(data["chat_id"]),
            user_id=int(data["user_id"]),
            source_message_id=data.get("source_message_id"),
            source_message_thread_id=data.get("source_message_thread_id"),
            data=data.get("data") or {},
            created_at=datetime.fromisoformat(data["created_at"]),
        )


class SessionStore:
    """Session store with optional Redis backend and in-memory fallback."""

    def __init__(
        self,
        *,
        session_key_prefix: str = DEFAULT_SESSION_KEY_PREFIX,
        callback_lock_key_prefix: str = DEFAULT_CALLBACK_LOCK_KEY_PREFIX,
        pending_input_key_prefix: str = DEFAULT_PENDING_INPUT_KEY_PREFIX,
    ) -> None:
        self._sessions: Dict[str, MenuSession] = {}
        self._callback_locks: Dict[str, datetime] = {}
        self._pending_inputs: Dict[str, PendingInput] = {}
        self._redis: Optional[Any] = None
        self._session_key_prefix = session_key_prefix
        self._callback_lock_key_prefix = callback_lock_key_prefix
        self._pending_input_key_prefix = pending_input_key_prefix

    def _redis_is_async(self) -> bool:
        return isinstance(self._redis, AsyncRedis)

    def _schedule_redis_op(self, coroutine) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = loop.create_task(coroutine)
        task.add_done_callback(lambda done: done.exception())

    def configure_redis(self, redis_url: str) -> None:
        """Enable Redis-backed storage."""
        client = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
            health_check_interval=30,
        )
        client.ping()
        self._redis = client

    async def configure_redis_async(self, redis_url: str) -> None:
        """Enable Redis-backed storage with an async client."""
        client = AsyncRedis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
            health_check_interval=30,
        )
        await client.ping()
        self._redis = client

    def disable_redis(self) -> None:
        """Disable Redis and fall back to in-memory storage."""
        if self._redis is not None:
            try:
                self._redis.close()
            except RedisError:
                pass
        self._redis = None

    async def disable_redis_async(self) -> None:
        """Disable Redis and fall back to in-memory storage."""
        if self._redis is not None:
            close = getattr(self._redis, "aclose", None)
            if callable(close):
                try:
                    await close()
                except RedisError:
                    pass
            else:
                try:
                    self._redis.close()
                except RedisError:
                    pass
        self._redis = None

    def using_redis(self) -> bool:
        """Return True when Redis is active for sessions."""
        return self._redis is not None

    def create_session(
        self,
        chat_id: int,
        message_id: int,
        user_id: int,
        message_thread_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new menu session."""
        self.cleanup_expired()
        session_id = str(uuid.uuid4())
        session = MenuSession(
            session_id=session_id,
            chat_id=chat_id,
            message_id=message_id,
            message_thread_id=message_thread_id,
            user_id=user_id,
            data=data or {},
        )
        self._sessions[session_id] = session
        self._trim_in_memory_sessions()
        if self._redis is not None:
            if self._redis_is_async():
                self._schedule_redis_op(
                    self._redis.setex(
                        f"{self._session_key_prefix}{session_id}",
                        SESSION_TTL_SECONDS,
                        session.to_json(),
                    )
                )
            else:
                self._redis.setex(
                    f"{self._session_key_prefix}{session_id}",
                    SESSION_TTL_SECONDS,
                    session.to_json(),
                )
        return session_id

    async def create_session_async(
        self,
        chat_id: int,
        message_id: int,
        user_id: int,
        message_thread_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new menu session with async Redis support."""
        self.cleanup_expired()
        session_id = str(uuid.uuid4())
        session = MenuSession(
            session_id=session_id,
            chat_id=chat_id,
            message_id=message_id,
            message_thread_id=message_thread_id,
            user_id=user_id,
            data=data or {},
        )
        self._sessions[session_id] = session
        self._trim_in_memory_sessions()
        if self._redis is not None:
            await self._redis.setex(
                f"{self._session_key_prefix}{session_id}",
                SESSION_TTL_SECONDS,
                session.to_json(),
            )
        return session_id

    def get_session(self, session_id: str) -> Optional[MenuSession]:
        """Get session by ID, return None if expired."""
        self.cleanup_expired()
        session = self._sessions.get(session_id)
        if session and session.is_expired():
            del self._sessions[session_id]
            return None
        if session is not None:
            return session

        if self._redis is not None and not self._redis_is_async():
            payload = self._redis.get(f"{self._session_key_prefix}{session_id}")
            if not payload:
                return None
            return MenuSession.from_json(payload)
        return None

    async def get_session_async(self, session_id: str) -> Optional[MenuSession]:
        """Get session by ID with async Redis support."""
        self.cleanup_expired()
        if self._redis is not None:
            payload = await self._redis.get(f"{self._session_key_prefix}{session_id}")
            if not payload:
                return self._sessions.get(session_id)
            session = MenuSession.from_json(payload)
            self._sessions[session_id] = session
            self._trim_in_memory_sessions()
            return session

        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> None:
        """Delete session by ID."""
        self._sessions.pop(session_id, None)
        if self._redis is not None:
            if self._redis_is_async():
                self._schedule_redis_op(self._redis.delete(f"{self._session_key_prefix}{session_id}"))
            else:
                self._redis.delete(f"{self._session_key_prefix}{session_id}")

    async def delete_session_async(self, session_id: str) -> None:
        """Delete session by ID with async Redis support."""
        self._sessions.pop(session_id, None)
        if self._redis is not None:
            await self._redis.delete(f"{self._session_key_prefix}{session_id}")

    def is_callback_locked(self, callback_query_id: str) -> bool:
        """Check if callback is already being processed."""
        self.cleanup_expired()
        lock_time = self._callback_locks.get(callback_query_id)
        if lock_time:
            if datetime.now(timezone.utc) - lock_time < timedelta(seconds=CALLBACK_LOCK_TTL_SECONDS):
                return True
            del self._callback_locks[callback_query_id]
        if self._redis is not None and not self._redis_is_async():
            return bool(self._redis.exists(f"{self._callback_lock_key_prefix}{callback_query_id}"))
        return False

    async def is_callback_locked_async(self, callback_query_id: str) -> bool:
        """Check if callback is already being processed with async Redis support."""
        self.cleanup_expired()
        if self.is_callback_locked(callback_query_id):
            return True
        if self._redis is not None:
            return bool(await self._redis.exists(f"{self._callback_lock_key_prefix}{callback_query_id}"))
        return False

    def lock_callback(self, callback_query_id: str) -> None:
        """Lock callback to prevent duplicate processing."""
        self.cleanup_expired()
        self._callback_locks[callback_query_id] = datetime.now(timezone.utc)
        self._trim_in_memory_callback_locks()
        if self._redis is not None:
            if self._redis_is_async():
                self._schedule_redis_op(
                    self._redis.set(
                        f"{self._callback_lock_key_prefix}{callback_query_id}",
                        "1",
                        ex=CALLBACK_LOCK_TTL_SECONDS,
                        nx=True,
                    )
                )
            else:
                self._redis.set(
                    f"{self._callback_lock_key_prefix}{callback_query_id}",
                    "1",
                    ex=CALLBACK_LOCK_TTL_SECONDS,
                    nx=True,
                )

    async def lock_callback_async(self, callback_query_id: str) -> None:
        """Lock callback to prevent duplicate processing with async Redis support."""
        self.cleanup_expired()
        self._callback_locks[callback_query_id] = datetime.now(timezone.utc)
        self._trim_in_memory_callback_locks()
        if self._redis is not None:
            await self._redis.set(
                f"{self._callback_lock_key_prefix}{callback_query_id}",
                "1",
                ex=CALLBACK_LOCK_TTL_SECONDS,
                nx=True,
            )

    def cleanup_expired(self) -> None:
        """Remove expired sessions and locks for in-memory backend."""
        expired_sessions = [
            sid for sid, session in self._sessions.items() if session.is_expired()
        ]
        for sid in expired_sessions:
            del self._sessions[sid]

        cutoff = datetime.now(timezone.utc) - timedelta(seconds=CALLBACK_LOCK_TTL_SECONDS)
        expired_locks = [
            cid for cid, lock_time in self._callback_locks.items() if lock_time < cutoff
        ]
        for cid in expired_locks:
            del self._callback_locks[cid]

        expired_pending_inputs = [
            key for key, pending in self._pending_inputs.items() if pending.is_expired()
        ]
        for key in expired_pending_inputs:
            del self._pending_inputs[key]

    def set_pending_input(
        self,
        *,
        action: str,
        chat_id: int,
        user_id: int,
        source_message_id: Optional[int] = None,
        source_message_thread_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store a pending text-input action for a user."""
        self.cleanup_expired()
        pending = PendingInput(
            action=action,
            chat_id=chat_id,
            user_id=user_id,
            source_message_id=source_message_id,
            source_message_thread_id=source_message_thread_id,
            data=data or {},
        )
        key = self._pending_input_key(chat_id, user_id)
        self._pending_inputs[key] = pending
        self._trim_in_memory_pending_inputs()
        if self._redis is not None:
            if self._redis_is_async():
                self._schedule_redis_op(
                    self._redis.setex(
                        f"{self._pending_input_key_prefix}{key}",
                        PENDING_INPUT_TTL_SECONDS,
                        pending.to_json(),
                    )
                )
            else:
                self._redis.setex(
                    f"{self._pending_input_key_prefix}{key}",
                    PENDING_INPUT_TTL_SECONDS,
                    pending.to_json(),
                )

    async def set_pending_input_async(
        self,
        *,
        action: str,
        chat_id: int,
        user_id: int,
        source_message_id: Optional[int] = None,
        source_message_thread_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store a pending text-input action with async Redis support."""
        self.cleanup_expired()
        pending = PendingInput(
            action=action,
            chat_id=chat_id,
            user_id=user_id,
            source_message_id=source_message_id,
            source_message_thread_id=source_message_thread_id,
            data=data or {},
        )
        key = self._pending_input_key(chat_id, user_id)
        self._pending_inputs[key] = pending
        self._trim_in_memory_pending_inputs()
        if self._redis is not None:
            await self._redis.setex(
                f"{self._pending_input_key_prefix}{key}",
                PENDING_INPUT_TTL_SECONDS,
                pending.to_json(),
            )

    def get_pending_input(self, *, chat_id: int, user_id: int) -> Optional[PendingInput]:
        """Return pending input for the given chat/user pair."""
        self.cleanup_expired()
        key = self._pending_input_key(chat_id, user_id)
        pending = self._pending_inputs.get(key)
        if pending and pending.is_expired():
            del self._pending_inputs[key]
            return None
        if pending is not None:
            return pending

        if self._redis is not None and not self._redis_is_async():
            payload = self._redis.get(f"{self._pending_input_key_prefix}{key}")
            if not payload:
                return None
            return PendingInput.from_json(payload)
        return None

    async def get_pending_input_async(self, *, chat_id: int, user_id: int) -> Optional[PendingInput]:
        """Return pending input with async Redis support."""
        self.cleanup_expired()
        key = self._pending_input_key(chat_id, user_id)
        if self._redis is not None:
            payload = await self._redis.get(f"{self._pending_input_key_prefix}{key}")
            if not payload:
                return self._pending_inputs.get(key)
            pending = PendingInput.from_json(payload)
            self._pending_inputs[key] = pending
            self._trim_in_memory_pending_inputs()
            return pending
        return self.get_pending_input(chat_id=chat_id, user_id=user_id)

    def clear_pending_input(self, *, chat_id: int, user_id: int) -> None:
        """Clear pending input for the given chat/user pair."""
        key = self._pending_input_key(chat_id, user_id)
        self._pending_inputs.pop(key, None)
        if self._redis is not None:
            if self._redis_is_async():
                self._schedule_redis_op(self._redis.delete(f"{self._pending_input_key_prefix}{key}"))
            else:
                self._redis.delete(f"{self._pending_input_key_prefix}{key}")

    async def clear_pending_input_async(self, *, chat_id: int, user_id: int) -> None:
        """Clear pending input with async Redis support."""
        key = self._pending_input_key(chat_id, user_id)
        self._pending_inputs.pop(key, None)
        if self._redis is not None:
            await self._redis.delete(f"{self._pending_input_key_prefix}{key}")

    def _pending_input_key(self, chat_id: int, user_id: int) -> str:
        return f"{chat_id}:{user_id}"

    def _trim_in_memory_sessions(self) -> None:
        if len(self._sessions) <= MAX_IN_MEMORY_SESSIONS:
            return
        overflow = len(self._sessions) - MAX_IN_MEMORY_SESSIONS
        oldest_ids = sorted(
            self._sessions,
            key=lambda session_id: self._sessions[session_id].created_at,
        )[:overflow]
        for session_id in oldest_ids:
            self._sessions.pop(session_id, None)

    def _trim_in_memory_callback_locks(self) -> None:
        if len(self._callback_locks) <= MAX_IN_MEMORY_CALLBACK_LOCKS:
            return
        overflow = len(self._callback_locks) - MAX_IN_MEMORY_CALLBACK_LOCKS
        oldest_ids = sorted(
            self._callback_locks,
            key=self._callback_locks.get,
        )[:overflow]
        for callback_id in oldest_ids:
            self._callback_locks.pop(callback_id, None)

    def _trim_in_memory_pending_inputs(self) -> None:
        if len(self._pending_inputs) <= MAX_IN_MEMORY_PENDING_INPUTS:
            return
        overflow = len(self._pending_inputs) - MAX_IN_MEMORY_PENDING_INPUTS
        oldest_keys = sorted(
            self._pending_inputs,
            key=lambda pending_key: self._pending_inputs[pending_key].created_at,
        )[:overflow]
        for pending_key in oldest_keys:
            self._pending_inputs.pop(pending_key, None)

    def reset(self) -> None:
        """Reset in-memory state for tests."""
        self._sessions.clear()
        self._callback_locks.clear()
        self._pending_inputs.clear()
        self.disable_redis()


# Global session store instance
session_store = SessionStore()
