# Derivatives context

Futures/perpetual endpoints are read-only context. V2 implements funding rate and change/z-score, open interest and change/momentum, funding/OI interaction, mark-index basis and basis change, plus a price/OI divergence candidate. No futures order, API key, leverage, or futures execution path exists.

Funding, mark and index price come from `/fapi/v1/premiumIndex`; open interest comes from `/fapi/v1/openInterest`. Exchange and receive timestamps remain distinct. A context newer than decision time or beyond the staleness budget is excluded. Research must fit rolling statistics only on each temporal training window.
