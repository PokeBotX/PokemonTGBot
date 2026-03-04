"""Session management for menu navigation."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional


@dataclass
class MenuSession:
    """Menu session data."""
    session_id: str
    chat_id: int
    message_id: int
    message_thread_id: Optional[int]
    user_id: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(init=False)
    
    def __post_init__(self):
        self.expires_at = self.created_at + timedelta(minutes=10)
    
    def is_expired(self) -> bool:
        """Check if session has expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    def matches_context(
        self, 
        chat_id: int, 
        message_id: int,
        message_thread_id: Optional[int] = None
    ) -> bool:
        """Check if session matches given context."""
        return (
            self.chat_id == chat_id
            and self.message_id == message_id
            and self.message_thread_id == message_thread_id
        )


class SessionStore:
    """In-memory store for menu sessions and callback locks."""
    
    def __init__(self):
        self._sessions: Dict[str, MenuSession] = {}
        self._callback_locks: Dict[str, datetime] = {}
    
    def create_session(
        self,
        chat_id: int,
        message_id: int,
        user_id: int,
        message_thread_id: Optional[int] = None,
    ) -> str:
        """Create a new menu session."""
        session_id = str(uuid.uuid4())
        session = MenuSession(
            session_id=session_id,
            chat_id=chat_id,
            message_id=message_id,
            message_thread_id=message_thread_id,
            user_id=user_id,
        )
        self._sessions[session_id] = session
        return session_id
    
    def get_session(self, session_id: str) -> Optional[MenuSession]:
        """Get session by ID, return None if expired."""
        session = self._sessions.get(session_id)
        if session and session.is_expired():
            del self._sessions[session_id]
            return None
        return session
    
    def delete_session(self, session_id: str) -> None:
        """Delete session by ID."""
        self._sessions.pop(session_id, None)
    
    def is_callback_locked(self, callback_query_id: str) -> bool:
        """Check if callback is already being processed."""
        lock_time = self._callback_locks.get(callback_query_id)
        if lock_time:
            # Lock expires after 10 seconds
            if datetime.now(timezone.utc) - lock_time < timedelta(seconds=10):
                return True
            else:
                del self._callback_locks[callback_query_id]
        return False
    
    def lock_callback(self, callback_query_id: str) -> None:
        """Lock callback to prevent duplicate processing."""
        self._callback_locks[callback_query_id] = datetime.now(timezone.utc)
    
    def cleanup_expired(self) -> None:
        """Remove expired sessions and locks."""
        # Cleanup expired sessions
        expired_sessions = [
            sid for sid, session in self._sessions.items()
            if session.is_expired()
        ]
        for sid in expired_sessions:
            del self._sessions[sid]
        
        # Cleanup old callback locks
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=10)
        expired_locks = [
            cid for cid, lock_time in self._callback_locks.items()
            if lock_time < cutoff
        ]
        for cid in expired_locks:
            del self._callback_locks[cid]


# Global session store instance
session_store = SessionStore()
