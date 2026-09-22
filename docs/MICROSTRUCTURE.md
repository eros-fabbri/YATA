# Microstructure V2

`features-v2-62dcdaf26bc1` is isolated from V1. At decision time `T`, only events whose exchange and receive timestamps are both `<= T` are eligible. A stale or invalid book yields no book-derived values; missing data is left missing, never replaced by zero.

| Feature | Definition / unit | Lookback |
|---|---|---|
| quoted/relative spread | ask-bid (quote currency), divided by mid | latest valid BBO |
| mid, microprice | `(bid+ask)/2`; size-weighted opposite quote | latest valid BBO |
| top imbalance | `(bid_qty-ask_qty)/(bid_qty+ask_qty)` | top level |
| depth/multilevel imbalance | same ratio over retained levels | latest valid book |
| bid/ask depth | summed base-asset quantity | retained levels |
| count, buy/sell volume | aggregate-trade observations and base quantity | trailing 60 s |
| trade/aggressive imbalance | `(buy-sell)/(buy+sell)` | trailing 60 s |
| trade/volume intensity | observations or volume per second | trailing 60 s |
| micro-volatility | square-root sum of squared log trade returns | trailing 60 s |
| price impact proxy | first-to-last trade-price change / volume | trailing 60 s |

Binance aggressor side is inferred from the aggregate trade buyer-maker flag. This is an observable trade-flow proxy, not the full matching engine.
