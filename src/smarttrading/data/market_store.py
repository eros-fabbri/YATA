from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from smarttrading.data.market_v2 import (
    AggregateTradeEvent,
    BBOEvent,
    DerivativesEvent,
    MarketContextSnapshot,
)
from smarttrading.domain import OrderBookSnapshot


class MarketDataStore:
    def __init__(self, database: str | Path, *, wal_checkpoint_pages: int = 1000) -> None:
        path = Path(database)
        if path.name == "forward_v1.db":
            raise ValueError("Shadow V2 must not use the Forward V1 database")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.execute(f"PRAGMA wal_autocheckpoint={wal_checkpoint_pages:d}")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS events("
            "id TEXT PRIMARY KEY,kind TEXT NOT NULL,event_ts TEXT NOT NULL,"
            "received_at TEXT NOT NULL,payload TEXT NOT NULL)"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS snapshots("
            "hash TEXT PRIMARY KEY,decision_ts TEXT NOT NULL,payload TEXT NOT NULL)"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS runtime_state("
            "key TEXT PRIMARY KEY,payload TEXT NOT NULL,updated_at TEXT NOT NULL)"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS trade_buckets("
            "asset TEXT NOT NULL,bucket_ts TEXT NOT NULL,first_event_ts TEXT NOT NULL,"
            "last_event_ts TEXT NOT NULL,last_received_at TEXT NOT NULL,"
            "trade_count INTEGER NOT NULL,"
            "buy_volume TEXT NOT NULL,sell_volume TEXT NOT NULL,first_price TEXT NOT NULL,"
            "last_price TEXT NOT NULL,min_price TEXT NOT NULL,max_price TEXT NOT NULL,"
            "PRIMARY KEY(asset,bucket_ts))"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS derived_snapshots("
            "asset TEXT NOT NULL,bucket_ts TEXT NOT NULL,feature_version TEXT NOT NULL,"
            "payload TEXT NOT NULL,PRIMARY KEY(asset,bucket_ts))"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS book_checkpoints("
            "asset TEXT NOT NULL,event_ts TEXT NOT NULL,received_at TEXT NOT NULL,"
            "sequence INTEGER NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(asset,event_ts))"
        )
        self.connection.commit()

    def append(self, event: AggregateTradeEvent | BBOEvent | DerivativesEvent) -> None:
        kind = (
            "trade"
            if isinstance(event, AggregateTradeEvent)
            else "bbo"
            if isinstance(event, BBOEvent)
            else "derivatives"
        )
        self.connection.execute(
            "INSERT OR IGNORE INTO events VALUES(?,?,?,?,?)",
            (
                event.event_id,
                kind,
                event.event_timestamp.isoformat(),
                event.received_at.isoformat(),
                event.model_dump_json(),
            ),
        )

    def save_snapshot(self, snapshot: MarketContextSnapshot) -> None:
        self.connection.execute(
            "INSERT OR IGNORE INTO snapshots VALUES(?,?,?)",
            (
                snapshot.snapshot_hash,
                snapshot.decision_time.isoformat(),
                snapshot.model_dump_json(),
            ),
        )

    def replay(self) -> tuple[AggregateTradeEvent | BBOEvent | DerivativesEvent, ...]:
        rows = self.connection.execute(
            "SELECT kind,payload FROM events ORDER BY event_ts,received_at,id"
        ).fetchall()
        result: list[AggregateTradeEvent | BBOEvent | DerivativesEvent] = []
        for kind, payload in rows:
            if kind == "trade":
                result.append(AggregateTradeEvent.model_validate_json(payload))
            elif kind == "bbo":
                result.append(BBOEvent.model_validate_json(payload))
            else:
                result.append(DerivativesEvent.model_validate_json(payload))
        return tuple(result)

    def snapshots(self) -> tuple[MarketContextSnapshot, ...]:
        rows = self.connection.execute(
            "SELECT payload FROM snapshots ORDER BY decision_ts,hash"
        ).fetchall()
        return tuple(MarketContextSnapshot.model_validate_json(row[0]) for row in rows)

    def close(self) -> None:
        self.flush(checkpoint=True)
        self.connection.close()

    def flush(self, *, checkpoint: bool = False) -> None:
        self.connection.commit()
        if checkpoint:
            self.connection.execute("PRAGMA wal_checkpoint(PASSIVE)")

    @staticmethod
    def _bucket(timestamp: datetime, seconds: int) -> str:
        epoch = int(timestamp.timestamp())
        return datetime.fromtimestamp(epoch - epoch % seconds, tz=UTC).isoformat()

    def aggregate_trade(self, event: AggregateTradeEvent, *, bucket_seconds: int = 1) -> None:
        bucket = self._bucket(event.event_timestamp, bucket_seconds)
        buy = event.quantity if event.side.value == "buy" else Decimal(0)
        sell = event.quantity if event.side.value == "sell" else Decimal(0)
        self.connection.execute(
            "INSERT INTO trade_buckets VALUES(?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(asset,bucket_ts) DO UPDATE SET "
            "last_event_ts=excluded.last_event_ts,last_received_at=excluded.last_received_at,"
            "trade_count=trade_count+1,"
            "buy_volume=CAST(buy_volume AS REAL)+CAST(excluded.buy_volume AS REAL),"
            "sell_volume=CAST(sell_volume AS REAL)+CAST(excluded.sell_volume AS REAL),"
            "last_price=excluded.last_price,"
            "min_price=MIN(CAST(min_price AS REAL),CAST(excluded.min_price AS REAL)),"
            "max_price=MAX(CAST(max_price AS REAL),CAST(excluded.max_price AS REAL))",
            (
                event.asset,
                bucket,
                event.event_timestamp.isoformat(),
                event.event_timestamp.isoformat(),
                event.received_at.isoformat(),
                1,
                str(buy),
                str(sell),
                str(event.price),
                str(event.price),
                str(event.price),
                str(event.price),
            ),
        )

    def save_bbo_sample(self, event: BBOEvent, *, bucket_seconds: int = 1) -> None:
        bucket = self._bucket(event.event_timestamp, bucket_seconds)
        sampled = event.model_copy(update={"event_id": f"bbo-sample:{event.asset}:{bucket}"})
        self.connection.execute(
            "INSERT INTO events VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
            "event_ts=excluded.event_ts,received_at=excluded.received_at,payload=excluded.payload",
            (
                sampled.event_id,
                "bbo",
                sampled.event_timestamp.isoformat(),
                sampled.received_at.isoformat(),
                sampled.model_dump_json(),
            ),
        )

    def save_derived_snapshot(
        self,
        snapshot: MarketContextSnapshot,
        features: dict[str, float],
        feature_version: str,
        *,
        bucket_seconds: int = 1,
    ) -> None:
        bucket = self._bucket(snapshot.decision_time, bucket_seconds)
        payload = {
            "decision_time": snapshot.decision_time.isoformat(),
            "asset": snapshot.asset,
            "features": features,
            "sources": {
                key: value.model_dump(mode="json") for key, value in snapshot.sources.items()
            },
        }
        self.connection.execute(
            "INSERT INTO derived_snapshots VALUES(?,?,?,?) ON CONFLICT(asset,bucket_ts) "
            "DO UPDATE SET feature_version=excluded.feature_version,payload=excluded.payload",
            (
                snapshot.asset,
                bucket,
                feature_version,
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
            ),
        )

    def save_book_checkpoint(
        self, book: OrderBookSnapshot, received_at: datetime, *, retained_levels: int = 20
    ) -> None:
        compact = {
            "bids": [[str(x.price), str(x.quantity)] for x in book.bids[:retained_levels]],
            "asks": [[str(x.price), str(x.quantity)] for x in book.asks[:retained_levels]],
        }
        self.connection.execute(
            "INSERT OR IGNORE INTO book_checkpoints VALUES(?,?,?,?,?)",
            (
                book.asset,
                book.timestamp.isoformat(),
                received_at.isoformat(),
                book.sequence,
                json.dumps(compact, separators=(",", ":")),
            ),
        )

    def compact_raw_retention(self, days: int) -> int:
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
        cursor = self.connection.execute("DELETE FROM events WHERE event_ts < ?", (cutoff,))
        return cursor.rowcount

    def compact_replay(self) -> dict[str, tuple[tuple[object, ...], ...]]:
        return {
            "trade_buckets": tuple(
                self.connection.execute("SELECT * FROM trade_buckets ORDER BY bucket_ts,asset")
            ),
            "derived_snapshots": tuple(
                self.connection.execute("SELECT * FROM derived_snapshots ORDER BY bucket_ts,asset")
            ),
            "book_checkpoints": tuple(
                self.connection.execute("SELECT * FROM book_checkpoints ORDER BY event_ts,asset")
            ),
        }

    def set_state(self, key: str, payload: dict[str, object]) -> None:
        self.connection.execute(
            "INSERT INTO runtime_state VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET "
            "payload=excluded.payload,updated_at=excluded.updated_at",
            (key, json.dumps(payload, sort_keys=True, default=str), datetime.now(UTC).isoformat()),
        )
        self.connection.commit()

    def get_state(self, key: str) -> dict[str, object] | None:
        row = self.connection.execute(
            "SELECT payload FROM runtime_state WHERE key=?", (key,)
        ).fetchone()
        return None if row is None else json.loads(row[0])

    def coverage(self) -> dict[str, object]:
        rows = self.connection.execute(
            "SELECT kind,payload,event_ts FROM events ORDER BY event_ts"
        ).fetchall()
        snapshots = self.connection.execute(
            "SELECT payload,decision_ts FROM snapshots ORDER BY decision_ts"
        ).fetchall()
        derived = self.connection.execute(
            "SELECT payload,bucket_ts FROM derived_snapshots ORDER BY bucket_ts"
        ).fetchall()
        trade_buckets = self.connection.execute(
            "SELECT asset,COUNT(*),MIN(bucket_ts),MAX(bucket_ts),SUM(trade_count) "
            "FROM trade_buckets GROUP BY asset"
        ).fetchall()
        checkpoints = self.connection.execute(
            "SELECT asset,COUNT(*),MIN(event_ts),MAX(event_ts) FROM book_checkpoints GROUP BY asset"
        ).fetchall()
        assets: dict[str, dict[str, object]] = {}
        for kind, payload, timestamp in rows:
            asset = str(json.loads(payload)["asset"])
            item = assets.setdefault(
                asset,
                {
                    "first_timestamp": timestamp,
                    "last_timestamp": timestamp,
                    "event_counts": {},
                    "funding_observations": 0,
                    "oi_observations": 0,
                    "feature_snapshots": 0,
                    "valid_book_snapshots": 0,
                },
            )
            item["last_timestamp"] = timestamp
            counts = item["event_counts"]
            assert isinstance(counts, dict)
            counts[kind] = int(counts.get(kind, 0)) + 1
            if kind == "derivatives":
                raw = json.loads(payload)
                item["funding_observations"] = int(str(item["funding_observations"])) + int(
                    raw.get("funding_rate") is not None
                )
                item["oi_observations"] = int(str(item["oi_observations"])) + int(
                    raw.get("open_interest") is not None
                )
        for payload, timestamp in snapshots:
            raw = json.loads(payload)
            asset = str(raw["asset"])
            item = assets.setdefault(
                asset,
                {
                    "first_timestamp": timestamp,
                    "last_timestamp": timestamp,
                    "event_counts": {},
                    "funding_observations": 0,
                    "oi_observations": 0,
                    "feature_snapshots": 0,
                    "valid_book_snapshots": 0,
                },
            )
            item["feature_snapshots"] = int(str(item["feature_snapshots"])) + 1
            item["valid_book_snapshots"] = int(str(item["valid_book_snapshots"])) + int(
                raw.get("book") is not None
            )
        for payload, timestamp in derived:
            raw = json.loads(payload)
            asset = str(raw["asset"])
            item = assets.setdefault(
                asset,
                {
                    "first_timestamp": timestamp,
                    "last_timestamp": timestamp,
                    "event_counts": {},
                    "funding_observations": 0,
                    "oi_observations": 0,
                    "feature_snapshots": 0,
                    "valid_book_snapshots": 0,
                },
            )
            item["first_timestamp"] = min(str(item["first_timestamp"]), timestamp)
            item["last_timestamp"] = max(str(item["last_timestamp"]), timestamp)
            item["feature_snapshots"] = int(str(item["feature_snapshots"])) + 1
            valid = raw.get("sources", {}).get("book", {}).get("validity") == "valid"
            item["valid_book_snapshots"] = int(str(item["valid_book_snapshots"])) + int(valid)
        for asset, buckets, first, last, trades in trade_buckets:
            item = assets.setdefault(
                asset,
                {
                    "first_timestamp": first,
                    "last_timestamp": last,
                    "event_counts": {},
                    "funding_observations": 0,
                    "oi_observations": 0,
                    "feature_snapshots": 0,
                    "valid_book_snapshots": 0,
                },
            )
            counts = item["event_counts"]
            assert isinstance(counts, dict)
            counts["trade_buckets"] = buckets
            counts["aggregated_trades"] = trades
        for asset, count, first, last in checkpoints:
            item = assets.setdefault(
                asset,
                {
                    "first_timestamp": first,
                    "last_timestamp": last,
                    "event_counts": {},
                    "funding_observations": 0,
                    "oi_observations": 0,
                    "feature_snapshots": 0,
                    "valid_book_snapshots": 0,
                },
            )
            counts = item["event_counts"]
            assert isinstance(counts, dict)
            counts["book_checkpoints"] = count
        runtime = self.get_state("runtime") or {}
        quality = runtime.get("quality", {})
        for item in assets.values():
            first = datetime.fromisoformat(str(item["first_timestamp"]))
            last = datetime.fromisoformat(str(item["last_timestamp"]))
            total = int(str(item["feature_snapshots"]))
            item["elapsed_seconds"] = max(0.0, (last - first).total_seconds())
            item["valid_book_percentage"] = (
                int(str(item["valid_book_snapshots"])) / total if total else 0.0
            )
            item["gaps"] = quality.get("sequence_gaps", 0) if isinstance(quality, dict) else 0
        return {"assets": assets, "generated_at": datetime.now(UTC).isoformat()}

    def retention_dry_run(self, raw_days: int, snapshot_days: int) -> dict[str, object]:
        now = datetime.now(UTC)
        raw_cutoff = (now - timedelta(days=raw_days)).isoformat()
        snapshot_cutoff = (now - timedelta(days=snapshot_days)).isoformat()
        raw = self.connection.execute(
            "SELECT COUNT(*) FROM events WHERE event_ts < ?", (raw_cutoff,)
        ).fetchone()[0]
        snapshots = self.connection.execute(
            "SELECT COUNT(*) FROM snapshots WHERE decision_ts < ?", (snapshot_cutoff,)
        ).fetchone()[0]
        return {
            "dry_run": True,
            "deleted": 0,
            "raw_eligible": raw,
            "snapshots_eligible": snapshots,
            "raw_cutoff": raw_cutoff,
            "snapshot_cutoff": snapshot_cutoff,
        }


def inspect_storage(database: str | Path) -> dict[str, object]:
    """Read-only physical/logical storage report; never checkpoints or migrates the database."""
    path = Path(database).resolve()
    connection = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    try:
        table_names = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        counts = {
            name: int(connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
            for name in table_names
        }
        physical = {
            str(name): int(size or 0)
            for name, size in connection.execute(
                "SELECT name,SUM(pgsize) FROM dbstat GROUP BY name ORDER BY SUM(pgsize) DESC"
            )
        }
        ranges: list[tuple[str | None, str | None]] = []
        for table, column in (
            ("events", "event_ts"),
            ("snapshots", "decision_ts"),
            ("trade_buckets", "bucket_ts"),
            ("derived_snapshots", "bucket_ts"),
            ("book_checkpoints", "event_ts"),
        ):
            if table in table_names:
                ranges.append(
                    connection.execute(
                        f'SELECT MIN("{column}"),MAX("{column}") FROM "{table}"'
                    ).fetchone()
                )
        starts = [datetime.fromisoformat(value) for value, _ in ranges if value]
        ends = [datetime.fromisoformat(value) for _, value in ranges if value]
        coverage = (max(ends) - min(starts)).total_seconds() if starts and ends else 0.0
        persisted_rows = sum(counts.values()) - counts.get("runtime_state", 0)
        source_counts = (
            {
                str(kind): int(count)
                for kind, count in connection.execute(
                    "SELECT kind,COUNT(*) FROM events GROUP BY kind"
                )
            }
            if "events" in table_names
            else {}
        )
        if counts.get("snapshots", 0) > counts.get("events", 0):
            source_counts["depth_inferred"] = counts["snapshots"] - counts["events"]
        incoming_events = max(counts.get("snapshots", 0), counts.get("events", 0))
        runtime_events = 0
        if "runtime_state" in table_names:
            runtime_row = connection.execute(
                "SELECT payload FROM runtime_state WHERE key='runtime'"
            ).fetchone()
            if runtime_row:
                runtime_events = int(json.loads(runtime_row[0]).get("events", 0))
                incoming_events = max(incoming_events, runtime_events)
        if not incoming_events:
            aggregated = (
                connection.execute(
                    "SELECT COALESCE(SUM(trade_count),0) FROM trade_buckets"
                ).fetchone()[0]
                if "trade_buckets" in table_names
                else 0
            )
            incoming_events = int(aggregated) + counts.get("events", 0)
        main_bytes = path.stat().st_size
        wal_path, shm_path = Path(f"{path}-wal"), Path(f"{path}-shm")
        total_bytes = main_bytes + (wal_path.stat().st_size if wal_path.exists() else 0)
        hourly = total_bytes / coverage * 3600 if coverage > 0 else None
        largest = [
            {"object": name, "bytes": size, "percent": size / main_bytes * 100}
            for name, size in sorted(physical.items(), key=lambda item: item[1], reverse=True)
        ]
        source_rates = {
            source: {"events": count, "events_per_second": count / coverage if coverage else None}
            for source, count in source_counts.items()
        }
        return {
            "database": str(path),
            "db_bytes": main_bytes,
            "wal_bytes": wal_path.stat().st_size if wal_path.exists() else 0,
            "shm_bytes": shm_path.stat().st_size if shm_path.exists() else 0,
            "rows": counts,
            "coverage_seconds": coverage,
            "incoming_events": incoming_events,
            "latest_runtime_events": runtime_events,
            "persisted_rows": persisted_rows,
            "source_rates": source_rates,
            "bytes_per_event": total_bytes / incoming_events if incoming_events else None,
            "bytes_per_persisted_row": total_bytes / persisted_rows if persisted_rows else None,
            "measured_mb_per_minute": hourly / 60_000_000 if hourly is not None else None,
            "measured_mb_per_hour": hourly / 1_000_000 if hourly is not None else None,
            "projected_gb_per_day": hourly * 24 / 1_000_000_000 if hourly is not None else None,
            "largest_objects": largest,
        }
    finally:
        connection.close()
