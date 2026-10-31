import logging
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory stores — reset on server restart (intentional: chat sessions are ephemeral).
_histories: dict[str, list[dict]] = {}
_schemas: dict[str, str] = {}
_pending_sql: dict[str, str] = {}

# Hard cap on messages per user to prevent unbounded memory growth.
# Oldest messages are trimmed first; the system prompt is prepended fresh each call
# so it is never stored here and never needs to be trimmed.
MAX_MESSAGES = 60


def get_history(user_id: str) -> list[dict]:
    """Return a copy of the full message history for this user (may be empty)."""
    return list(_histories.get(user_id, []))


def append_messages(user_id: str, *messages: dict) -> None:
    """Append one or more messages to the user's history, then trim if over the cap."""
    history = _histories.setdefault(user_id, [])
    history.extend(messages)
    if len(history) > MAX_MESSAGES:
        trimmed = len(history) - MAX_MESSAGES
        # Keep complete user rounds so no orphaned tool responses are sent.
        boundary = next((i for i in range(trimmed, len(history))
                         if history[i].get("role") == "user"), None)
        if boundary is not None:
            del history[:boundary]
        logger.debug("user=%s  History trimmed by %d message(s) (cap=%d)", user_id, trimmed, MAX_MESSAGES)


def get_pending_tool_call_id(user_id: str) -> Optional[str]:
    """
    Scan history in reverse to find the last assistant message that has tool_calls.
    Returns the id of the first tool call in that message, or None if not found.

    Used by /chat/execute to resume after a user approves or rejects a write query:
    the assistant's tool-call message is already in history, and we need its
    tool_call_id to build the matching tool-result message.
    """
    for msg in reversed(_histories.get(user_id, [])):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            return msg["tool_calls"][0]["id"]
    return None


def get_schema(user_id: str) -> Optional[str]:
    """Return the cached schema text for this user, or None if not cached."""
    return _schemas.get(user_id)


def set_schema(user_id: str, schema_text: str) -> None:
    """Cache the schema text for this user."""
    _schemas[user_id] = schema_text
    logger.debug("user=%s  Schema cached (%d chars)", user_id, len(schema_text))


def get_pending_sql(user_id: str) -> Optional[str]:
    """Return the server-stored pending SQL awaiting user approval, or None."""
    return _pending_sql.get(user_id)


def set_pending_sql(user_id: str, sql: str) -> None:
    """Store the SQL that is paused awaiting user approval."""
    _pending_sql[user_id] = sql
    logger.debug("user=%s  Pending SQL stored (%d chars)", user_id, len(sql))


def clear_pending_sql(user_id: str) -> None:
    """Remove the pending SQL after it has been approved or rejected."""
    _pending_sql.pop(user_id, None)


def clear(user_id: str) -> None:
    """
    Clear the history and schema cache for this user.
    Called on (re-)onboarding so the new connection starts with a clean slate.
    """
    _histories.pop(user_id, None)
    _schemas.pop(user_id, None)
    _pending_sql.pop(user_id, None)
    logger.info("user=%s  History and schema cache cleared", user_id)


def invalidate_schema(user_id: str) -> None:
    _schemas.pop(user_id, None)
