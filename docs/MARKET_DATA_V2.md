# Market data V2

Public Binance inputs are spot `aggTrade`, `bookTicker`, and `depth@100ms` combined WebSocket streams, REST `/api/v3/depth` snapshots, and public futures premium-index/open-interest REST endpoints. WebSockets use protocol ping/pong, reconnect with capped exponential backoff, and expose reconnect counts.

The local book applies an update only when `U <= lastUpdateId+1 <= u`. Duplicate IDs and old updates are rejected. Any sequence gap marks the book INVALID; features remain unavailable until a fresh REST snapshot. Starting a stream after a snapshot may expose a race, but the first gap causes a safe resync rather than fabricated continuity.

The compact SQLite store processes every depth delta in memory but does not persist those deltas. Trades are aggregated into deterministic one-second buckets with count, first/last/min/max price, and buy/sell volume. BBO is sampled at most once per asset/second. Funding/OI is stored only when its value changes. Derived feature/source-quality snapshots are stored once per asset/second without embedding the rolling trade window or full book. A 20-level book checkpoint is retained every 60 seconds and after resync.

Writes are committed in one-second batches. WAL uses `synchronous=NORMAL`, automatic checkpointing and an explicit passive checkpoint every 60 seconds and at graceful shutdown. Raw BBO/derivatives retention defaults to seven days and is configurable; trade buckets, derived snapshots and book checkpoints are retained for research. The runtime never deletes legacy full snapshots automatically.

Compact replay deterministically orders sampled BBO, derivatives, trade buckets, derived feature snapshots and periodic book checkpoints. It supports research at the persisted sampling cadence and verification of derived inputs. It is explicitly **not tick-perfect replay** and cannot reconstruct every intermediate matching-engine or depth state.
