"""Small SQLite persistence layer for webhook events and policy audit records."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DATABASE = Path(__file__).resolve().parent.parent / "data" / "recoverpay.db"


def database_path() -> str:
    return os.getenv("RECOVERPAY_DB_PATH", str(DEFAULT_DATABASE))


def connect() -> sqlite3.Connection:
    path = Path(database_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS webhook_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            classification TEXT NOT NULL,
            decision TEXT NOT NULL,
            received_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL,
            reason TEXT NOT NULL,
            actor TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    return connection


def save_webhook_event(
    event_id: str,
    event_type: str,
    payload: dict[str, Any],
    classification: dict[str, Any],
    decision: dict[str, Any],
) -> bool:
    connection = connect()
    try:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO webhook_events
            (event_id, event_type, payload, classification, decision, received_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_type,
                json.dumps(payload),
                json.dumps(classification),
                json.dumps(decision),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.execute(
            """
            INSERT INTO audit_log (event_id, action, status, reason, actor, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                "classify_and_policy",
                "duplicate" if cursor.rowcount == 0 else "recorded",
                classification.get("normalized_reason", "needs_human_review"),
                "razorpay_webhook",
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


def list_audit_events(limit: int = 50) -> list[dict[str, Any]]:
    connection = connect()
    try:
        rows = connection.execute(
            """
            SELECT event_id, action, status, reason, actor, created_at
            FROM audit_log ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()
