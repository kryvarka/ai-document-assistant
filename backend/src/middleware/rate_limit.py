import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status

from src.config import settings
from src.db.models import User
from src.middleware.auth import get_current_user
from src.middleware.logging import get_logger

logger = get_logger(__name__)


class SlidingWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        hits = self._hits[key]

        while hits and now - hits[0] >= self._window:
            hits.popleft()

        if len(hits) >= self._limit:
            return False, max(1, int(self._window - (now - hits[0])))

        hits.append(now)
        return True, 0

    def reset(self) -> None:
        self._hits.clear()


_chat_limiter = SlidingWindowRateLimiter(
    limit=settings.rate_limit_chat_per_minute, window_seconds=60
)
_upload_limiter = SlidingWindowRateLimiter(
    limit=settings.rate_limit_upload_per_minute, window_seconds=60
)
_auth_limiter = SlidingWindowRateLimiter(
    limit=settings.rate_limit_auth_per_minute, window_seconds=60
)


def _enforce(limiter: SlidingWindowRateLimiter, key: str, scope: str) -> None:
    allowed, retry_after = limiter.check(key)
    if allowed:
        return
    logger.warning("rate_limit_exceeded", scope=scope, key=key, retry_after=retry_after)
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Rate limit exceeded. Retry in {retry_after}s.",
        headers={"Retry-After": str(retry_after)},
    )


def rate_limit_chat(current_user: User = Depends(get_current_user)) -> User:
    _enforce(_chat_limiter, current_user.id, "chat")
    return current_user


def rate_limit_upload(current_user: User = Depends(get_current_user)) -> User:
    _enforce(_upload_limiter, current_user.id, "upload")
    return current_user


def rate_limit_auth(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    _enforce(_auth_limiter, client_host, "auth")


def reset_all_limiters() -> None:
    for limiter in (_chat_limiter, _upload_limiter, _auth_limiter):
        limiter.reset()
