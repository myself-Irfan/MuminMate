from fastapi import status
from httpx import AsyncClient


async def test_register_success(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "new@example.com", "username": "newuser", "password": "password123"},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["username"] == "newuser"
    assert "password" not in body["user"]


async def test_register_duplicate_email(client: AsyncClient, registered_user: dict):
    resp = await client.post(
        "/api/auth/register",
        json={"email": registered_user["email"], "username": "other", "password": "password123"},
    )
    assert resp.status_code == status.HTTP_409_CONFLICT


async def test_register_short_password(client: AsyncClient):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "username": "shortpw", "password": "abc"},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_login_success(client: AsyncClient, registered_user: dict):
    resp = await client.post("/api/auth/login", json=registered_user)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"
    assert "refresh_token" in resp.cookies
    assert body["user"]["email"] == registered_user["email"]


async def test_login_wrong_password(client: AsyncClient, registered_user: dict):
    resp = await client.post(
        "/api/auth/login",
        json={"email": registered_user["email"], "password": "wrongpassword"},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


async def test_login_unknown_email(client: AsyncClient):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


async def test_login_lockout(client: AsyncClient, registered_user: dict):
    for _ in range(5):
        await client.post(
            "/api/auth/login",
            json={"email": registered_user["email"], "password": "wrongpassword"},
        )
    resp = await client.post("/api/auth/login", json=registered_user)
    assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in resp.headers


async def test_me_authenticated(auth_client: AsyncClient, registered_user: dict):
    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["email"] == registered_user["email"]


async def test_me_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


async def test_refresh(auth_client: AsyncClient):
    resp = await auth_client.post("/api/auth/refresh")
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"
    assert "refresh_token" in resp.cookies


async def test_refresh_no_cookie(client: AsyncClient):
    resp = await client.post("/api/auth/refresh")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


async def test_logout(auth_client: AsyncClient):
    resp = await auth_client.post("/api/auth/logout")
    assert resp.status_code == status.HTTP_200_OK
    # Client discards the token — server cannot revoke a stateless JWT
    auth_client.headers.pop("Authorization", None)
    resp2 = await auth_client.get("/api/auth/me")
    assert resp2.status_code == status.HTTP_401_UNAUTHORIZED
