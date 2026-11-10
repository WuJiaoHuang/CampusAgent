from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


class ConversationMemory:
    """Small SQLite checkpointer with opaque, user-scoped conversation keys."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS conversations ("
            "key TEXT PRIMARY KEY, messages TEXT NOT NULL)"
        )
        self._db.commit()

    @staticmethod
    def user_key(jwt: str, session_id: str) -> str:
        digest = hashlib.sha256(jwt.encode()).hexdigest()
        return f"{digest}:{session_id}"

    def load(self, key: str) -> list[dict[str, str]]:
        row = self._db.execute("SELECT messages FROM conversations WHERE key=?", (key,)).fetchone()
        if not row:
            return []
        import json
        return json.loads(row[0])

    def save(self, key: str, messages: list[dict[str, str]]) -> None:
        import json
        payload = json.dumps(messages, ensure_ascii=False)
        self._db.execute(
            "INSERT OR REPLACE INTO conversations(key,messages) VALUES (?,?)",
            (key, payload),
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._db
