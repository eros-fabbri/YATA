# Market data

Historical and reconciliation data use Binance public REST; closed real-time candles use the public
combined WebSocket stream with heartbeat, reconnect and exponential backoff. Reconnection invokes a
REST reconciliation callback before streaming resumes. Duplicate IDs and out-of-order candles are
discarded, while gaps are explicitly recorded. An in-progress kline (`x=false`) never reaches
features or strategy logic.

For a decision at time `T`, a bar is eligible only if `bar_open + timeframe <= T`. This rule applies
independently to 5m, 15m, 1h and 4h. Cross-asset BTC/ETH features inner-join already eligible bars by
timestamp; a later observation from either asset cannot change earlier context.

The domain supports trades, best bid/ask, order-book snapshots, funding and open interest. Funding
and open interest are derivatives context features only; spot paper execution remains spot. Public
availability varies by venue and the system records absence rather than fabricating values.

Microstructure features are causal summaries of the supplied snapshots/trades. They do not imply
knowledge of hidden liquidity, queue position, intrabar order-book evolution or fill probability.

