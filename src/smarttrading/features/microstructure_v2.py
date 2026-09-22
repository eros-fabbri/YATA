from __future__ import annotations

import hashlib
import itertools
import json
import math
from datetime import timedelta

from smarttrading.data.market_v2 import MarketContextSnapshot

FEATURE_VERSION_V2 = "features-v2-" + hashlib.sha256(b"m10-market-intelligence-v2").hexdigest()[:12]


def microstructure_features(context: MarketContextSnapshot) -> dict[str, float]:
    result: dict[str, float] = {}
    quote, book, trades = context.quote, context.book, context.trades
    if quote is not None:
        mid = float((quote.bid + quote.ask) / 2)
        spread = float(quote.ask - quote.bid)
        total = float(quote.bid_quantity + quote.ask_quantity)
        result.update(quoted_spread=spread, relative_spread=spread / mid, mid_price=mid)
        if total:
            result["top_of_book_imbalance"] = float(quote.bid_quantity - quote.ask_quantity) / total
            result["microprice"] = float(
                (quote.ask * quote.bid_quantity + quote.bid * quote.ask_quantity)
                / (quote.bid_quantity + quote.ask_quantity)
            )
    if book is not None and book.bids and book.asks:
        bid_depth = float(sum(x.quantity for x in book.bids))
        ask_depth = float(sum(x.quantity for x in book.asks))
        total = bid_depth + ask_depth
        result.update(bid_depth=bid_depth, ask_depth=ask_depth)
        if total:
            result["depth_imbalance"] = (bid_depth - ask_depth) / total
            result["multi_level_imbalance"] = result["depth_imbalance"]
    if trades:
        buy = sum(float(x.quantity) for x in trades if x.side.value == "buy")
        sell = sum(float(x.quantity) for x in trades if x.side.value == "sell")
        volume = buy + sell
        window = max(
            (context.decision_time - min(x.timestamp for x in trades)).total_seconds(), 1.0
        )
        result.update(
            trade_count=float(len(trades)),
            buy_initiated_volume=buy,
            sell_initiated_volume=sell,
            trade_intensity=len(trades) / window,
            volume_intensity=volume / window,
        )
        if volume:
            result["trade_imbalance"] = (buy - sell) / volume
            result["aggressive_volume_imbalance"] = result["trade_imbalance"]
        prices = [float(x.price) for x in trades]
        returns = [math.log(right / left) for left, right in itertools.pairwise(prices)]
        if returns:
            result["realized_micro_volatility"] = math.sqrt(sum(x * x for x in returns))
        if len(prices) > 1 and volume:
            result["short_term_price_impact"] = (prices[-1] - prices[0]) / volume
    return result


def derivatives_features(history: tuple[MarketContextSnapshot, ...]) -> dict[str, float]:
    values = [x.derivatives for x in history if x.derivatives is not None]
    if not values:
        return {}
    current = values[-1]
    result: dict[str, float] = {}
    funding = [x.funding_rate for x in values if x.funding_rate is not None]
    oi = [float(x.open_interest) for x in values if x.open_interest is not None]
    basis = [
        float((x.mark_price - x.index_price) / x.index_price)
        for x in values
        if x.mark_price and x.index_price
    ]
    if current.funding_rate is not None:
        result["funding_rate"] = current.funding_rate
        if len(funding) > 1:
            mean = sum(funding) / len(funding)
            std = (sum((x - mean) ** 2 for x in funding) / len(funding)) ** 0.5
            result.update(
                funding_z_score=(funding[-1] - mean) / std if std else 0.0,
                funding_change=funding[-1] - funding[-2],
            )
    if current.open_interest is not None:
        result["open_interest"] = float(current.open_interest)
        if len(oi) > 1:
            change = oi[-1] - oi[-2]
            result.update(
                open_interest_change=change,
                open_interest_momentum=change / oi[-2] if oi[-2] else 0.0,
            )
    if basis:
        result["mark_index_basis"] = basis[-1]
        if len(basis) > 1:
            result["basis_change"] = basis[-1] - basis[-2]
    if funding and oi:
        result["funding_oi_interaction"] = funding[-1] * oi[-1]
    micro = microstructure_features(history[-1])
    if len(oi) > 1 and "mid_price" in micro:
        result["price_oi_divergence"] = math.copysign(1.0, micro["mid_price"]) * -math.copysign(
            1.0, oi[-1] - oi[-2]
        )
    return result


def feature_definition_hash() -> str:
    return hashlib.sha256(
        json.dumps(
            {"version": FEATURE_VERSION_V2, "trade_lookback": str(timedelta(seconds=60))},
            sort_keys=True,
        ).encode()
    ).hexdigest()
