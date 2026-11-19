from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any


class PendingActionStore:
    """Small durable ledger for confirmation-gated external write operations."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False, timeout=5)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS pending_actions ("
            "operation_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, user_id TEXT NOT NULL, "
            "tool_name TEXT NOT NULL, arguments_json TEXT NOT NULL, summary_json TEXT NOT NULL, "
            "status TEXT NOT NULL, result_json TEXT, "
            "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        self._connection.commit()

    def create(
        self,
        *,
        thread_id: str,
        user_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        operation_id = str(uuid.uuid4())
        self._connection.execute(
            "INSERT INTO pending_actions(operation_id,thread_id,user_id,tool_name,arguments_json,"
            "summary_json,status) VALUES (?,?,?,?,?,?, 'PREPARED')",
            (
                operation_id,
                thread_id,
                user_id,
                tool_name,
                json.dumps(arguments, ensure_ascii=False, sort_keys=True),
                json.dumps(summary, ensure_ascii=False),
            ),
        )
        self._connection.commit()
        return {
            "operation_id": operation_id,
            "tool_name": tool_name,
            "arguments": arguments,
            **summary,
        }

    def get(self, operation_id: str, thread_id: str, user_id: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT tool_name,arguments_json,summary_json,status,result_json,created_at "
            "FROM pending_actions "
            "WHERE operation_id=? AND thread_id=? AND user_id=?",
            (operation_id, thread_id, user_id),
        ).fetchone()
        if row is None:
            return None
        return {
            "operation_id": operation_id,
            "tool_name": row[0],
            "arguments": json.loads(row[1]),
            **json.loads(row[2]),
            "status": row[3],
            "result": json.loads(row[4]) if row[4] else None,
            "created_at": row[5],
        }

    def get_pending(self, thread_id: str, user_id: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "SELECT operation_id FROM pending_actions WHERE thread_id=? AND user_id=? "
            "AND status IN ('PREPARED','CONFIRMED','EXECUTING') ORDER BY created_at DESC LIMIT 1",
            (thread_id, user_id),
        ).fetchone()
        return self.get(row[0], thread_id, user_id) if row else None

    def approve(self, operation_id: str, thread_id: str, user_id: str) -> bool:
        cursor = self._connection.execute(
            "UPDATE pending_actions SET status='CONFIRMED',updated_at=CURRENT_TIMESTAMP "
            "WHERE operation_id=? AND thread_id=? AND user_id=? AND status='PREPARED'",
            (operation_id, thread_id, user_id),
        )
        self._connection.commit()
        return cursor.rowcount == 1

    def reject(self, operation_id: str, thread_id: str, user_id: str) -> bool:
        cursor = self._connection.execute(
            "UPDATE pending_actions SET status='REJECTED',updated_at=CURRENT_TIMESTAMP "
            "WHERE operation_id=? AND thread_id=? AND user_id=? AND status='PREPARED'",
            (operation_id, thread_id, user_id),
        )
        self._connection.commit()
        return cursor.rowcount == 1

    def begin_execution(self, operation_id: str, thread_id: str, user_id: str) -> bool:
        cursor = self._connection.execute(
            "UPDATE pending_actions SET status='EXECUTING',updated_at=CURRENT_TIMESTAMP "
            "WHERE operation_id=? AND thread_id=? AND user_id=? AND status='CONFIRMED'",
            (operation_id, thread_id, user_id),
        )
        self._connection.commit()
        return cursor.rowcount == 1

    def finish(
        self,
        operation_id: str,
        thread_id: str,
        user_id: str,
        status: str,
        result: dict[str, Any],
    ) -> None:
        cursor = self._connection.execute(
            "UPDATE pending_actions SET status=?,result_json=?,updated_at=CURRENT_TIMESTAMP "
            "WHERE operation_id=? AND thread_id=? AND user_id=?",
            (status, json.dumps(result, ensure_ascii=False), operation_id, thread_id, user_id),
        )
        self._connection.commit()
        if cursor.rowcount != 1:
            raise RuntimeError("操作状态持久化失败")

    def close(self) -> None:
        self._connection.close()
