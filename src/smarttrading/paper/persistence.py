from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class PaperStore:
    """SQLite append-only event journal plus atomic latest-state snapshots."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
              event_id TEXT PRIMARY KEY,
              event_type TEXT NOT NULL,
              timestamp TEXT NOT NULL,
              payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS events_type_time ON events(event_type, timestamp);
            CREATE TABLE IF NOT EXISTS state (
              key TEXT PRIMARY KEY,
              payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS models (
              model_version TEXT PRIMARY KEY,
              status TEXT NOT NULL CHECK(status IN ('candidate','paper','retired')),
              payload TEXT NOT NULL,
              promoted_at TEXT
            );
            """
        )
        self._connection.commit()

    def append(
        self, event_id: str, event_type: str, timestamp: str, payload: dict[str, Any]
    ) -> bool:
        cursor = self._connection.execute(
            "INSERT OR IGNORE INTO events(event_id,event_type,timestamp,payload) VALUES(?,?,?,?)",
            (event_id, event_type, timestamp, json.dumps(payload, sort_keys=True, default=str)),
        )
        self._connection.commit()
        return cursor.rowcount == 1

    def exists(self, event_id: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM events WHERE event_id=?", (event_id,)
        ).fetchone()
        return row is not None

    def events(self, event_type: str | None = None) -> list[dict[str, Any]]:
        if event_type is None:
            rows = self._connection.execute(
                "SELECT * FROM events ORDER BY timestamp,event_id"
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM events WHERE event_type=? ORDER BY timestamp,event_id", (event_type,)
            ).fetchall()
        return [
            {
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "timestamp": row["timestamp"],
                "payload": json.loads(row["payload"]),
            }
            for row in rows
        ]

    def set_state(self, key: str, payload: dict[str, Any]) -> None:
        self._connection.execute(
            "INSERT INTO state(key,payload) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET payload=excluded.payload",
            (key, json.dumps(payload, sort_keys=True, default=str)),
        )
        self._connection.commit()

    def get_state(self, key: str) -> dict[str, Any] | None:
        row = self._connection.execute("SELECT payload FROM state WHERE key=?", (key,)).fetchone()
        return None if row is None else json.loads(row["payload"])

    def close(self) -> None:
        self._connection.close()
