"""Dedicated session store for the admin bot."""

from bot.navigation.session import SessionStore

admin_session_store = SessionStore(
    session_key_prefix="admin_menu_session:",
    callback_lock_key_prefix="admin_callback_lock:",
    pending_input_key_prefix="admin_pending_input:",
)

