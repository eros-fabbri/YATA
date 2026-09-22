from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from smarttrading.domain import Bar


class DatasetManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    dataset_id: str
    asset: str
    timeframe: str
    start: datetime
    end: datetime
    rows: int
    sha256: str


def build_manifest(bars: Sequence[Bar]) -> DatasetManifest:
    if not bars:
        raise ValueError("cannot manifest an empty dataset")
    payload = "\n".join(
        json.dumps(bar.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        for bar in bars
    ).encode()
    digest = hashlib.sha256(payload).hexdigest()
    first, last = bars[0], bars[-1]
    return DatasetManifest(
        dataset_id=f"{first.asset.replace('/', '-')}-{first.timeframe}-{digest[:12]}",
        asset=first.asset,
        timeframe=first.timeframe,
        start=first.timestamp,
        end=last.timestamp,
        rows=len(bars),
        sha256=digest,
    )
