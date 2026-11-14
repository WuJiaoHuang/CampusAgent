from __future__ import annotations

import hashlib


class ConversationMemory:
    """Compatibility namespace for stable, user-scoped LangGraph thread IDs.

    Conversation messages are persisted only by LangGraph's checkpointer. This
    helper intentionally owns no database connection and stores no messages.
    """

    @staticmethod
    def user_key(user_id: str, session_id: str) -> str:
        """Return the existing opaque checkpoint thread identifier."""
        digest = hashlib.sha256(str(user_id).encode()).hexdigest()
        return f"{digest}:{session_id}"
