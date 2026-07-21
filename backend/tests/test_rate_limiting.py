import pytest_asyncio
from fastapi import status
from httpx import AsyncClient

from backend.config import settings
from backend.limiter import limiter


@pytest_asyncio.fixture
async def rate_limiting_enabled():
    """`conftest.py` disables the limiter globally for every other test — these
    tests need it on, and need a clean bucket so earlier tests can't bleed in."""
    limiter.reset()
    limiter.enabled = True
    yield
    limiter.enabled = False
    limiter.reset()


async def _register_and_login(client: AsyncClient, email: str, username: str) -> str:
    payload = {"email": email, "username": username, "password": "password123"}
    await client.post("/api/auth/register", json=payload)
    resp = await client.post("/api/auth/login", json=payload)
    return resp.json()["access_token"]


async def test_login_enforces_configured_limit(client: AsyncClient, rate_limiting_enabled):
    payload = {"email": "limited@example.com", "username": "limited", "password": "password123"}
    await client.post("/api/auth/register", json=payload)

    for _ in range(settings.login_count_in_minutes):
        resp = await client.post("/api/auth/login", json=payload)
        assert resp.status_code == status.HTTP_200_OK
        assert "X-RateLimit-Limit" in resp.headers

    resp = await client.post("/api/auth/login", json=payload)
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in resp.headers


async def test_threads_create_enforces_configured_limit(
    auth_client: AsyncClient, rate_limiting_enabled
):
    for _ in range(settings.rate_limit_threads_create_count):
        resp = await auth_client.post("/api/threads", json={})
        assert resp.status_code == status.HTTP_201_CREATED

    resp = await auth_client.post("/api/threads", json={})
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in resp.headers


async def test_register_is_rate_limited(client: AsyncClient, rate_limiting_enabled):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "hdr@example.com", "username": "hdruser", "password": "password123"},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.headers["X-RateLimit-Limit"] == str(settings.register_count_in_minutes)


async def test_refresh_keyed_by_token_not_shared_ip(client: AsyncClient, rate_limiting_enabled):
    """Both users hit the endpoint through the same test client, so they share
    the same (fake) IP. If the key ever fell back to IP, the second user would
    see a lower remaining count from the first user's usage."""
    token_a = await _register_and_login(client, "refresh-a@example.com", "refresha")
    client.headers.update({"Authorization": f"Bearer {token_a}"})
    resp_a = await client.post("/api/auth/refresh")
    assert resp_a.status_code == status.HTTP_200_OK
    remaining_a = int(resp_a.headers["X-RateLimit-Remaining"])

    token_b = await _register_and_login(client, "refresh-b@example.com", "refreshb")
    client.headers.update({"Authorization": f"Bearer {token_b}"})
    resp_b = await client.post("/api/auth/refresh")
    assert resp_b.status_code == status.HTTP_200_OK
    remaining_b = int(resp_b.headers["X-RateLimit-Remaining"])

    assert remaining_a == remaining_b


async def test_threads_create_keyed_by_user_not_shared_ip(
    client: AsyncClient, rate_limiting_enabled
):
    token_a = await _register_and_login(client, "create-a@example.com", "createa")
    client.headers.update({"Authorization": f"Bearer {token_a}"})
    resp_a = await client.post("/api/threads", json={})
    remaining_a = int(resp_a.headers["X-RateLimit-Remaining"])

    token_b = await _register_and_login(client, "create-b@example.com", "createb")
    client.headers.update({"Authorization": f"Bearer {token_b}"})
    resp_b = await client.post("/api/threads", json={})
    remaining_b = int(resp_b.headers["X-RateLimit-Remaining"])

    assert remaining_a == remaining_b


async def test_logout_has_no_rate_limit(auth_client: AsyncClient, rate_limiting_enabled):
    resp = await auth_client.post("/api/auth/logout")
    assert resp.status_code == status.HTTP_200_OK
    assert "X-RateLimit-Limit" not in resp.headers


async def test_me_has_no_rate_limit(auth_client: AsyncClient, rate_limiting_enabled):
    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == status.HTTP_200_OK
    assert "X-RateLimit-Limit" not in resp.headers


async def test_list_threads_has_no_rate_limit(auth_client: AsyncClient, rate_limiting_enabled):
    resp = await auth_client.get("/api/threads")
    assert resp.status_code == status.HTTP_200_OK
    assert "X-RateLimit-Limit" not in resp.headers


async def test_get_thread_has_no_rate_limit(auth_client: AsyncClient, rate_limiting_enabled):
    create_resp = await auth_client.post("/api/threads", json={"title": "x"})
    thread_id = create_resp.json()["id"]
    resp = await auth_client.get(f"/api/threads/{thread_id}")
    assert resp.status_code == status.HTTP_200_OK
    assert "X-RateLimit-Limit" not in resp.headers
