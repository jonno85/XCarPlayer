"""Health check endpoint with per-IP rate limiting."""

import time
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request

from app.store import playlist_jobs, track_jobs

router = APIRouter(tags=["health"])

# Allow at most LIMIT calls per WINDOW_SECONDS from the same IP
_LIMIT = 10
_WINDOW_SECONDS = 60

# ip -> deque of call timestamps (seconds)
_call_log: dict[str, deque] = defaultdict(deque)


def _check_rate_limit(ip: str) -> None:
    now = time.monotonic()
    window_start = now - _WINDOW_SECONDS
    calls = _call_log[ip]

    # Drop timestamps outside the window
    while calls and calls[0] < window_start:
        calls.popleft()

    if len(calls) >= _LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests — max {_LIMIT} per {_WINDOW_SECONDS}s",
        )

    calls.append(now)


@router.get("/health")
def health(request: Request) -> dict:
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(ip)

    return {
        "status": "ok",
        "track_jobs": len(track_jobs),
        "playlist_jobs": len(playlist_jobs),
    }
