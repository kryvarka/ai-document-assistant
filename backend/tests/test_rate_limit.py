import pytest

from src.middleware.rate_limit import SlidingWindowRateLimiter


def test_limiter_allows_up_to_the_limit_then_blocks():
    limiter = SlidingWindowRateLimiter(limit=3, window_seconds=60)

    assert [limiter.check("user-a")[0] for _ in range(3)] == [True, True, True]

    allowed, retry_after = limiter.check("user-a")
    assert allowed is False
    assert retry_after > 0


def test_limiter_tracks_keys_independently():
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)

    assert limiter.check("user-a")[0] is True
    assert limiter.check("user-a")[0] is False
    assert limiter.check("user-b")[0] is True


def test_limiter_window_expires(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr("src.middleware.rate_limit.time.monotonic", lambda: clock["now"])
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)

    assert limiter.check("user-a")[0] is True
    assert limiter.check("user-a")[0] is False

    clock["now"] += 61
    assert limiter.check("user-a")[0] is True


@pytest.mark.asyncio
async def test_login_attempts_are_throttled(client, monkeypatch):
    from src.middleware import rate_limit

    monkeypatch.setattr(
        rate_limit, "_auth_limiter", SlidingWindowRateLimiter(limit=2, window_seconds=60)
    )

    payload = {"email": "nobody@docqa.ai", "password": "guessing"}
    first = await client.post("/api/auth/login", json=payload)
    second = await client.post("/api/auth/login", json=payload)
    third = await client.post("/api/auth/login", json=payload)

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429
    assert "Retry-After" in third.headers


@pytest.mark.asyncio
async def test_uploads_are_throttled_per_user(client, stub_vector_store, monkeypatch):
    from src.middleware import rate_limit

    monkeypatch.setattr(
        rate_limit, "_upload_limiter", SlidingWindowRateLimiter(limit=1, window_seconds=60)
    )

    registration = await client.post(
        "/api/auth/register",
        json={"name": "Busy", "email": "busy@docqa.ai", "password": "password123"},
    )
    headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
    upload = {"file": ("a.txt", b"Some indexable content here.", "text/plain")}

    assert (
        await client.post("/api/documents/upload", headers=headers, files=upload)
    ).status_code == 202
    assert (
        await client.post("/api/documents/upload", headers=headers, files=upload)
    ).status_code == 429
