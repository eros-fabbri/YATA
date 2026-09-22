from __future__ import annotations

from collections.abc import Sequence

from smarttrading.domain import BestBidAsk, OrderBookSnapshot, Trade


def order_book_features(book: OrderBookSnapshot) -> dict[str, float]:
    if not book.bids or not book.asks:
        return {}
    bid, ask = book.bids[0], book.asks[0]
    total_top = bid.quantity + ask.quantity
    bid_depth = sum((level.quantity for level in book.bids), start=bid.quantity * 0)
    ask_depth = sum((level.quantity for level in book.asks), start=ask.quantity * 0)
    total_depth = bid_depth + ask_depth
    microprice = (
        (ask.price * bid.quantity + bid.price * ask.quantity) / total_top
        if total_top
        else (bid.price + ask.price) / 2
    )
    return {
        "bid_ask_spread": float(ask.price - bid.price),
        "order_book_imbalance": float((bid.quantity - ask.quantity) / total_top)
        if total_top
        else 0.0,
        "depth_imbalance": float((bid_depth - ask_depth) / total_depth) if total_depth else 0.0,
        "microprice": float(microprice),
    }


def quote_features(quote: BestBidAsk) -> dict[str, float]:
    midpoint = (quote.bid + quote.ask) / 2
    return {"relative_spread": float((quote.ask - quote.bid) / midpoint)}


def trade_features(trades: Sequence[Trade], window_seconds: float) -> dict[str, float]:
    if not trades or window_seconds <= 0:
        return {}
    buy = sum(float(trade.quantity) for trade in trades if trade.side.value == "buy")
    sell = sum(float(trade.quantity) for trade in trades if trade.side.value == "sell")
    total = buy + sell
    return {
        "trade_buy_sell_imbalance": (buy - sell) / total if total else 0.0,
        "aggressive_volume_imbalance": (buy - sell) / total if total else 0.0,
        "trade_intensity": len(trades) / window_seconds,
    }
