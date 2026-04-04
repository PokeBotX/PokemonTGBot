"""Unit tests for session management."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from bot.navigation.session import PendingInput, SessionStore


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.closed = False

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = value

    def get(self, key: str):
        return self.store.get(key)

    def delete(self, key: str) -> None:
        self.store.pop(key, None)

    def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> None:
        if nx and key in self.store:
            return
        self.store[key] = value

    def exists(self, key: str) -> bool:
        return key in self.store

    def close(self) -> None:
        self.closed = True


def test_create_session():
    """Test session creation with UUID4."""
    store = SessionStore()
    
    session_id = store.create_session(
        chat_id=12345,
        message_id=100,
        user_id=67890,
        message_thread_id=None,
    )
    
    # Check session_id is UUID string
    assert isinstance(session_id, str)
    assert len(session_id) == 36  # UUID4 format
    assert "-" in session_id
    
    # Check session exists
    session = store.get_session(session_id)
    assert session is not None
    assert session.chat_id == 12345
    assert session.message_id == 100
    assert session.user_id == 67890
    assert session.message_thread_id is None


def test_session_expiration():
    """Test that session expires after TTL (10 minutes)."""
    store = SessionStore()
    
    # Create session
    session_id = store.create_session(
        chat_id=12345,
        message_id=100,
        user_id=67890,
    )
    
    # Session should exist now
    session = store.get_session(session_id)
    assert session is not None
    
    # Manually set expires_at to past
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    
    # Session should be expired (is_expired property)
    assert session.is_expired() is True


def test_get_expired_session():
    """Test that get_session returns None for expired session."""
    store = SessionStore()
    
    session_id = store.create_session(
        chat_id=12345,
        message_id=100,
        user_id=67890,
    )
    
    # Manually set expires_at to past
    session = store._sessions[session_id]
    session.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    
    # get_session should return None
    result = store.get_session(session_id)
    assert result is None


def test_session_matches_context():
    """Test session context matching."""
    store = SessionStore()
    
    session_id = store.create_session(
        chat_id=12345,
        message_id=100,
        user_id=67890,
        message_thread_id=42,
    )
    
    session = store.get_session(session_id)
    
    # Exact match
    assert session.matches_context(12345, 100, 42) is True
    
    # Wrong chat_id
    assert session.matches_context(99999, 100, 42) is False
    
    # Wrong message_id
    assert session.matches_context(12345, 999, 42) is False
    
    # Wrong thread_id
    assert session.matches_context(12345, 100, 99) is False
    
    # None vs None thread_id
    session_id2 = store.create_session(
        chat_id=12345,
        message_id=200,
        user_id=67890,
        message_thread_id=None,
    )
    session2 = store.get_session(session_id2)
    assert session2.matches_context(12345, 200, None) is True


def test_callback_locking():
    """Test duplicate callback prevention (10 sec TTL)."""
    store = SessionStore()
    
    callback_id = "callback_123"
    
    # First lock should succeed
    store.lock_callback(callback_id)
    assert store.is_callback_locked(callback_id) is True
    
    # Second lock attempt should still show as locked
    store.lock_callback(callback_id)
    assert store.is_callback_locked(callback_id) is True
    
    # Wait 11 seconds (mock time)
    future_time = datetime.now(timezone.utc) + timedelta(seconds=11)
    with patch('bot.navigation.session.datetime') as mock_datetime:
        mock_datetime.now.return_value = future_time
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        
        # Lock should be expired, cleanup should remove it
        store.cleanup_expired()
        assert store.is_callback_locked(callback_id) is False


def test_cleanup_expired():
    """Test cleanup removes old sessions and locks."""
    store = SessionStore()
    
    # Create 3 sessions
    session_id1 = store.create_session(chat_id=1, message_id=1, user_id=1)
    session_id2 = store.create_session(chat_id=2, message_id=2, user_id=2)
    session_id3 = store.create_session(chat_id=3, message_id=3, user_id=3)
    
    # Create 2 callback locks
    store.lock_callback("callback_1")
    store.lock_callback("callback_2")
    
    # Manually expire session1 and callback_1
    store._sessions[session_id1].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    store._callback_locks["callback_1"] = datetime.now(timezone.utc) - timedelta(seconds=11)
    
    # Before cleanup
    assert len(store._sessions) == 3
    assert len(store._callback_locks) == 2
    
    # Run cleanup
    store.cleanup_expired()
    
    # After cleanup
    assert len(store._sessions) == 2  # session1 removed
    assert len(store._callback_locks) == 1  # callback_1 removed
    
    # Check remaining sessions
    assert store.get_session(session_id1) is None
    assert store.get_session(session_id2) is not None
    assert store.get_session(session_id3) is not None
    
    # Check remaining locks
    assert store.is_callback_locked("callback_1") is False
    assert store.is_callback_locked("callback_2") is True


def test_delete_session():
    """Test manual session deletion."""
    store = SessionStore()
    
    session_id = store.create_session(
        chat_id=12345,
        message_id=100,
        user_id=67890,
    )
    
    # Session should exist
    assert store.get_session(session_id) is not None
    
    # Delete session
    store.delete_session(session_id)
    
    # Session should be gone
    assert store.get_session(session_id) is None


def test_session_store_redis_backend_roundtrip() -> None:
    store = SessionStore()
    store._redis = FakeRedis()

    session_id = store.create_session(chat_id=5, message_id=10, user_id=15)
    session = store.get_session(session_id)

    assert session is not None
    assert session.chat_id == 5
    assert session.message_id == 10
    store.delete_session(session_id)
    assert store.get_session(session_id) is None


def test_pending_input_redis_backend_roundtrip() -> None:
    store = SessionStore()
    store._redis = FakeRedis()

    store.set_pending_input(
        action="cover_search",
        chat_id=5,
        user_id=15,
        source_message_id=99,
        data={"query": "pikachu"},
    )
    pending = store.get_pending_input(chat_id=5, user_id=15)

    assert isinstance(pending, PendingInput)
    assert pending.action == "cover_search"
    assert pending.data["query"] == "pikachu"

    store.clear_pending_input(chat_id=5, user_id=15)
    assert store.get_pending_input(chat_id=5, user_id=15) is None
