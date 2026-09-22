# Shadow V2

Shadow V2 is observation-only and isolated from Forward V1. It rejects a database named `forward_v1.db`, has no execution/portfolio/risk/order dependency, and persists to `data/shadow_v2.db` by default. Artifacts may move only `CANDIDATE -> SHADOW`; no automatic PAPER promotion exists.

Run manually:

```bash
uv run smarttrading shadow run --database data/shadow_v2.db --assets BTC/USDT ETH/USDT
```

The runner writes human-readable operational messages to stderr and structured JSON lines to a rotating file (`logs/shadow_v2.log`, 10 MB, five backups by default). Configure this with `--log-level`, `--log-file`, `--log-max-bytes`, and `--log-backups`. A database-specific PID file prevents concurrent writers. SIGINT/SIGTERM stop collection, flush SQLite, save final state, close the feed and remove the PID file.

Operations and collection maturity:

```bash
uv run smarttrading shadow status --database data/shadow_v2.db
uv run smarttrading shadow health --database data/shadow_v2.db
uv run smarttrading shadow coverage --database data/shadow_v2.db
uv run smarttrading shadow readiness --database data/shadow_v2.db
uv run smarttrading shadow retention --database data/shadow_v2.db
uv run smarttrading shadow storage --database data/shadow_v2.db
```

Health exits with 0 for healthy, 1 for degraded/stopped/stale, and 2 for unsafe/failed. Readiness is informational and assesses only technical data maturity. Retention is always a dry run: it reports eligible rows but deletes nothing.

Storage guardrails begin only after a five-minute measurement window, avoiding false alarms from SQLite/WAL initialization. Defaults are WARNING at 100 MB/hour and DEGRADED at 250 MB/hour. DEGRADED suspends sampled raw BBO persistence while the in-memory book, sequence validation, trade aggregation, derived snapshots and decision safety continue. Thresholds and suspension behavior are configurable from `shadow run`.

Latency is reported separately for each asset and source. Aggregate-trade and depth latency use Binance exchange timestamps. `bookTicker` has no exchange event timestamp, so BBO latency is explicitly unavailable rather than reported as a misleading near-zero value. The status also exposes each source's age/validity and the last WebSocket disconnect type, close code, reason, connection lifetime, and retry backoff.

On every WebSocket connection generation, the runner reconciles both books with REST while stream messages buffer. Updates already covered by the snapshot are counted as `pre_snapshot_discards`, not out-of-order events; the first bridging update must satisfy Binance sequence rules. Operational health becomes DEGRADED for high stale ratio, source p95 above five seconds, or excessive reconnect/gap rate, and UNSAFE while any local book is invalid.

For a bounded diagnostic use `--max-events 1000 --max-seconds 60`. The final JSON reports events/sec, CPU seconds, peak RSS, extrapolated storage/hour, reconnects, resyncs/gaps/duplicates/out-of-order observations, stale/missing ratios and source latency percentiles. Do not infer profitability from collection health.
