from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status

from .audit import privacy_hash
from .config import Settings, get_settings

_lock = Lock()
_buckets: dict[str, deque[float]] = defaultdict(deque)


def client_key(request: Request, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    host = forwarded or (request.client.host if request.client else "unknown")
    token_hint = request.headers.get("x-aida-access-token")
    return privacy_hash(f"{host}:{token_hint or ''}", settings) or "unknown"


def enforce_rate_limit(
    request: Request,
    *,
    bucket: str,
    limit: int,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    if not settings.rate_limit_enabled:
        return

    key = f"{bucket}:{client_key(request, settings)}"
    now = time.time()
    cutoff = now - settings.rate_limit_window_seconds

    with _lock:
        entries = _buckets[key]
        while entries and entries[0] <= cutoff:
            entries.popleft()
        if len(entries) >= limit:
            retry_after = max(1, int(entries[0] + settings.rate_limit_window_seconds - now))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please wait before retrying.",
                headers={"Retry-After": str(retry_after)},
            )
        entries.append(now)
