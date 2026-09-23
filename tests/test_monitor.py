from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from smarttrading.monitor.alerts import monitor_alerts
from smarttrading.monitor.app import (
    _v2_panel,
    age_seconds,
    calculate_spread_bps,
    collect_snapshot,
    format_funding,
    format_market_price,
    format_spread_bps,
    run_monitor,
)
from smarttrading.monitor.rates import SessionRates
from smarttrading.monitor.readers import read_v1, read_v2


def _v1_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        "CREATE TABLE events("
        "event_id TEXT PRIMARY KEY,event_type TEXT,timestamp TEXT,payload TEXT);"
        "CREATE INDEX events_type_time ON events(event_type,timestamp);"
        "CREATE TABLE state(key TEXT PRIMARY KEY,payload TEXT);"
    )
    now = datetime.now(UTC).isoformat()
    lock = {
        "experiment_id": "forward-v1",
        "metadata": {"experiment_started_at": now},
    }
    paper = {"cash": "1000", "equity": "1002", "positions": {"BTC/USDT": "0.1"}}
    connection.executemany(
        "INSERT INTO state VALUES(?,?)",
        (
            ("forward_experiment", json.dumps(lock)),
            ("paper", json.dumps(paper)),
            ("paper_health", json.dumps({"state": "HEALTHY", "reasons": []})),
        ),
    )
    prediction = {
        "asset": "BTC/USDT",
        "prediction_timestamp": now,
        "probability_up": 0.61,
        "model_probabilities": {"logistic": 0.58, "gradient_boosting": 0.64},
        "confidence": 0.22,
        "disagreement": 0.06,
    }
    decision = {
        "asset": "BTC/USDT",
        "timestamp": now,
        "decision": "buy",
        "estimated_edge": 0.002,
        "estimated_transaction_cost": 0.0014,
    }
    connection.executemany(
        "INSERT INTO events VALUES(?,?,?,?)",
        (
            ("p1", "forward_prediction", now, json.dumps(prediction)),
            ("d1", "decision", now, json.dumps(decision)),
        ),
    )
    connection.commit()
    connection.close()


def _v2_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE runtime_state(key TEXT PRIMARY KEY,payload TEXT,updated_at TEXT)"
    )
    now = datetime.now(UTC).isoformat()
    runtime = {
        "shadow_id": "shadow-v2",
        "health": "HEALTHY",
        "feed_state": "CONNECTED",
        "updated_at": now,
        "latest_snapshot": now,
        "events": 100,
        "events_per_second": 40.0,
        "assets": {
            "BTC/USDT": {
                "bbo": {
                    "bid": "86486.38000000",
                    "ask": "86486.39000000",
                    "bid_quantity": "1",
                    "ask_quantity": "2",
                },
                "book_valid": True,
                "funding": "0.00000937",
                "open_interest": "100",
                "sources": {},
            }
        },
        "quality": {
            "reconnects": 2,
            "sequence_gaps": 3,
            "book_resync_count": 3,
            "out_of_order_events": 4,
            "duplicate_events": 0,
            "missing_ratio": 0,
            "stale_ratio": 0,
        },
        "source_latency": {"trade": {"p50_ms": 1, "p95_ms": 2}},
        "storage": {"mb_per_hour": 15.0, "projected_gb_per_day": 0.36},
        "storage_guardrail": "NORMAL",
        "persistence": {"raw_bbo_enabled": True},
    }
    manifest = {
        "shadow_id": "shadow-v2",
        "feature_version": "microstructure-v2",
        "start_timestamp": now,
    }
    connection.executemany(
        "INSERT INTO runtime_state VALUES(?,?,?)",
        (("runtime", json.dumps(runtime), now), ("manifest", json.dumps(manifest), now)),
    )
    connection.commit()
    connection.close()


def test_v1_v2_and_combined_modes(tmp_path: Path) -> None:
    v1_path, v2_path = tmp_path / "v1.db", tmp_path / "v2.db"
    _v1_database(v1_path)
    _v2_database(v2_path)
    assert read_v1(str(v1_path))["experiment_id"] == "forward-v1"
    assert read_v2(str(v2_path))["shadow_id"] == "shadow-v2"
    combined = collect_snapshot(str(v1_path), str(v2_path), SessionRates(started=0))
    assert combined["v1"]["available"] is True
    assert combined["v2"]["available"] is True


def test_missing_and_malformed_databases_remain_offline(tmp_path: Path) -> None:
    missing = read_v1(str(tmp_path / "missing.db"))
    assert missing["available"] is False
    malformed = tmp_path / "malformed.db"
    malformed.write_bytes(b"not sqlite")
    assert read_v2(str(malformed))["available"] is False


def test_timestamp_freshness_supports_timezone() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert age_seconds("2025-12-31T23:59:55+00:00", now) == 5
    assert age_seconds("invalid", now) is None


def test_v2_market_values_use_decimal_runtime_fields() -> None:
    spread = calculate_spread_bps("86486.38000000", "86486.39000000")
    assert spread is not None
    assert spread == Decimal("0.01") / Decimal("86486.385") * Decimal(10_000)
    assert format_market_price("86486.38000000") == "86486.38"
    assert format_market_price("2756.57000000") == "2756.57"
    assert format_spread_bps(spread) == "0.00115625"


def test_funding_preserves_tiny_zero_and_missing_values() -> None:
    assert format_funding("0.00000937") == "0.00000937"
    assert format_funding("0.00007929") == "0.00007929"
    assert format_funding("0") == "0.00000000"
    assert format_funding(None) == "N/A"


def test_invalid_or_missing_bbo_is_na_without_crashing() -> None:
    assert calculate_spread_bps("invalid", "1") is None
    assert calculate_spread_bps(None, None) is None
    assert calculate_spread_bps("0", "1") is None
    assert format_market_price("invalid") == "N/A"
    assert format_market_price(None) == "N/A"
    assert format_spread_bps(None) == "N/A"


def test_extremely_tight_nonzero_spread_stays_visible() -> None:
    spread = calculate_spread_bps("100000.00000000", "100000.00000001")
    assert spread is not None and spread > 0
    assert format_spread_bps(spread) != "0"


def test_v2_panel_renders_real_bbo_shape_quantities_and_funding() -> None:
    runtime = {
        "available": True,
        "database": "shadow.db",
        "database_bytes": 1,
        "runtime": {
            "assets": {
                "BTC/USDT": {
                    "bbo": {
                        "bid": "86486.38000000",
                        "ask": "86486.39000000",
                        "bid_quantity": "1.09100000",
                        "ask_quantity": "7.69903000",
                    },
                    "book_valid": True,
                    "funding": "0.00000937",
                }
            }
        },
    }
    output = StringIO()
    Console(file=output, width=120, color_system=None).print(_v2_panel(runtime, {}))
    rendered = output.getvalue()
    assert "86486.38" in rendered
    assert "86486.39" in rendered
    assert "1.09100000" in rendered
    assert "7.69903000" in rendered
    assert "0.00000937" in rendered


def test_rates_and_counter_reset() -> None:
    rates = SessionRates(started=100)
    first = rates.observe({"reconnects": 10}, now=100)
    second = rates.observe({"reconnects": 12}, now=3700)
    reset = rates.observe({"reconnects": 1}, now=7300)
    assert first["reconnects"]["per_hour"] is None
    assert second["reconnects"] == {"value": 12, "delta": 2, "per_hour": 2}
    assert reset["reconnects"]["delta"] == 0


def test_alert_generation_keeps_system_health_separate() -> None:
    old = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    v2 = {
        "available": True,
        "runtime": {
            "health": "HEALTHY",
            "assets": {"BTC/USDT": {"book_valid": False, "funding": None, "open_interest": None}},
            "quality": {"stale_ratio": 0.75},
            "source_latency": {"depth": {"p95_ms": 48_181}},
        },
    }
    alerts = monitor_alerts(None, v2, {}, {"v2_update": age_seconds(old)})
    assert len(alerts) >= 4
    assert v2["runtime"]["health"] == "HEALTHY"


def test_repeated_reads_never_modify_databases(tmp_path: Path) -> None:
    v1_path, v2_path = tmp_path / "v1.db", tmp_path / "v2.db"
    _v1_database(v1_path)
    _v2_database(v2_path)
    before = (v1_path.read_bytes(), v2_path.read_bytes())
    for _ in range(3):
        collect_snapshot(str(v1_path), str(v2_path), SessionRates())
    assert (v1_path.read_bytes(), v2_path.read_bytes()) == before
    assert not Path(f"{v1_path}-wal").exists()
    assert not Path(f"{v2_path}-wal").exists()


@pytest.mark.parametrize("mode", ["v1", "v2", "combined"])
def test_once_human_output(tmp_path: Path, capsys: pytest.CaptureFixture[str], mode: str) -> None:
    v1_path, v2_path = tmp_path / "v1.db", tmp_path / "v2.db"
    _v1_database(v1_path)
    _v2_database(v2_path)
    run_monitor(
        v1_db=str(v1_path) if mode != "v2" else None,
        v2_db=str(v2_path) if mode != "v1" else None,
        refresh=1,
        once=True,
        json_output=False,
        diagnostic_output=False,
    )
    assert "MONITOR WARNINGS" in capsys.readouterr().out


def test_json_and_diagnostic_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "v2.db"
    _v2_database(path)
    run_monitor(
        v1_db=None,
        v2_db=str(path),
        refresh=1,
        once=False,
        json_output=True,
        diagnostic_output=False,
    )
    assert json.loads(capsys.readouterr().out)["v2"]["available"] is True
    run_monitor(
        v1_db=None,
        v2_db=str(path),
        refresh=1,
        once=False,
        json_output=False,
        diagnostic_output=True,
    )
    assert json.loads(capsys.readouterr().out)["kind"] == "smarttrading-monitor-diagnostic"


def test_requires_database_and_positive_refresh() -> None:
    with pytest.raises(ValueError, match="at least one"):
        run_monitor(
            v1_db=None, v2_db=None, refresh=1, once=True, json_output=False, diagnostic_output=False
        )
    with pytest.raises(ValueError, match="positive"):
        run_monitor(
            v1_db="x", v2_db=None, refresh=0, once=True, json_output=False, diagnostic_output=False
        )
