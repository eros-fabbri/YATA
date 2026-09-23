from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


def _connect(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=0.2)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA busy_timeout=200")
    return connection


def _payload(connection: sqlite3.Connection, table: str, key: str) -> dict[str, Any] | None:
    row = connection.execute(f"SELECT payload FROM {table} WHERE key=?", (key,)).fetchone()
    return None if row is None else dict(json.loads(row[0]))


def _latest_events(
    connection: sqlite3.Connection, event_type: str, limit: int = 1
) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT timestamp,payload FROM events WHERE event_type=? "
        "ORDER BY timestamp DESC,event_id DESC LIMIT ?",
        (event_type, limit),
    ).fetchall()
    return [{"timestamp": row[0], "payload": json.loads(row[1])} for row in rows]


def _event_counts(connection: sqlite3.Connection) -> dict[str, int]:
    wanted = (
        "decision",
        "forward_outcome",
        "order",
        "fill",
        "trade",
        "risk_decision",
    )
    placeholders = ",".join("?" for _ in wanted)
    rows = connection.execute(
        f"SELECT event_type,COUNT(*) FROM events WHERE event_type IN ({placeholders}) "
        "GROUP BY event_type",
        wanted,
    ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def read_v1(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    try:
        with closing(_connect(path)) as connection:
            lock = _payload(connection, "state", "forward_experiment")
            paper = _payload(connection, "state", "paper") or {}
            health = _payload(connection, "state", "paper_health")
            counts = _event_counts(connection)
            predictions = _latest_events(connection, "forward_prediction", 20)
            decisions = _latest_events(connection, "decision", 20)
            equity = _latest_events(connection, "equity_snapshot")
            shadow_equity = _latest_events(connection, "shadow_equity_snapshot", 50)
            latest_by_asset: dict[str, dict[str, Any]] = {}
            for row in predictions:
                payload = dict(row["payload"])
                asset = str(payload.get("asset", "UNKNOWN"))
                latest_by_asset.setdefault(asset, payload)
            decision_by_asset: dict[str, dict[str, Any]] = {}
            for row in decisions:
                payload = dict(row["payload"])
                asset = str(payload.get("asset", "UNKNOWN"))
                decision_by_asset.setdefault(asset, payload)
            started = None
            experiment_id = None
            if lock:
                experiment_id = lock.get("experiment_id")
                metadata = lock.get("metadata")
                if isinstance(metadata, dict):
                    started = metadata.get("experiment_started_at")
            latest_equity = dict(equity[0]["payload"]) if equity else {}
            baselines: dict[str, dict[str, Any]] = {}
            for row in shadow_equity:
                payload = dict(row["payload"])
                strategy = str(payload.get("strategy", "UNKNOWN"))
                baselines.setdefault(strategy, payload)
            return {
                "available": True,
                "database": str(path),
                "database_bytes": path.stat().st_size,
                "experiment_id": experiment_id,
                "started_at": started,
                "feed": "offline_snapshot",
                "health": health,
                "paper": paper,
                "equity": latest_equity,
                "baselines": baselines,
                "counts": counts,
                "predictions": latest_by_asset,
                "decisions": decision_by_asset,
                "last_update": decisions[0]["timestamp"] if decisions else started,
                "error": None,
            }
    except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as error:
        return {
            "available": False,
            "database": str(path),
            "database_bytes": path.stat().st_size if path.is_file() else 0,
            "error": f"{type(error).__name__}: {error}",
        }


def read_v2(path_value: str) -> dict[str, Any]:
    path = Path(path_value)
    try:
        with closing(_connect(path)) as connection:
            runtime = _payload(connection, "runtime_state", "runtime") or {}
            manifest = _payload(connection, "runtime_state", "manifest") or {}
            started = manifest.get("start_timestamp")
            return {
                "available": True,
                "database": str(path),
                "database_bytes": sum(
                    candidate.stat().st_size
                    for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm"))
                    if candidate.exists()
                ),
                "shadow_id": runtime.get("shadow_id", manifest.get("shadow_id")),
                "feature_version": runtime.get("feature_version", manifest.get("feature_version")),
                "started_at": started,
                "runtime": runtime,
                "manifest": manifest,
                "last_update": runtime.get("updated_at"),
                "error": None,
            }
    except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as error:
        return {
            "available": False,
            "database": str(path),
            "database_bytes": path.stat().st_size if path.is_file() else 0,
            "error": f"{type(error).__name__}: {error}",
        }
