from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    signals_url: str = "https://signals.gitdealflow.com/api/signals.json"
    request_timeout_seconds: int = 20
    cache_ttl_seconds: int = 1800


settings = Settings()
