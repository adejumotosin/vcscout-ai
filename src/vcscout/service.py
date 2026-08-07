from __future__ import annotations

from time import time
from typing import Any

import pandas as pd

from .config import settings
from .data import dataset_metadata, fetch_live_payload, flatten_startups
from .scoring import deduplicate_for_ranking, score_startups

_CACHE: dict[str, Any] = {"ts": 0.0, "payload": None}


def get_payload(force_refresh: bool = False) -> dict[str, Any]:
    now = time()
    if (
        not force_refresh
        and _CACHE["payload"] is not None
        and now - float(_CACHE["ts"]) < settings.cache_ttl_seconds
    ):
        return _CACHE["payload"]
    payload = fetch_live_payload()
    _CACHE.update({"ts": now, "payload": payload})
    return payload


def get_ranked_startups(force_refresh: bool = False) -> tuple[pd.DataFrame, dict[str, Any]]:
    payload = get_payload(force_refresh=force_refresh)
    flat = flatten_startups(payload)
    scored = score_startups(flat)
    ranked = deduplicate_for_ranking(scored)
    return ranked, dataset_metadata(payload)
