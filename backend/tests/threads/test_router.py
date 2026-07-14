from fastapi import status
from httpx import AsyncClient


async def _login(client: AsyncClient, email: str, username: str) -> str:
    payload = {"email": email, "username": username, "password": "password123"}
    await client.post("/api/auth/register", json=payload)
    resp = await client.post("/api/auth/login", json=payload)
    return resp.json()["access_token"]


async def test_create_thread_default_title(auth_client: AsyncClient):
    resp = await auth_client.post("/api/threads", json={})
    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()
    assert body["title"] == "New thread"
    assert "id" in body
    assert "created_at" in body
    assert "expires_at" in body


async def test_create_thread_custom_title(auth_client: AsyncClient):
    resp = await auth_client.post("/api/threads", json={"title": "My thread"})
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.json()["title"] == "My thread"


async def test_create_thread_blank_title(auth_client: AsyncClient):
    resp = await auth_client.post("/api/threads", json={"title": "   "})
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


async def test_create_thread_unauthenticated(client: AsyncClient):
    resp = await client.post("/api/threads", json={})
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


async def test_list_threads(auth_client: AsyncClient):
    await auth_client.post("/api/threads", json={"title": "First"})
    await auth_client.post("/api/threads", json={"title": "Second"})
    resp = await auth_client.get("/api/threads")
    assert resp.status_code == status.HTTP_200_OK
    titles = {t["title"] for t in resp.json()}
    assert titles == {"First", "Second"}


async def test_list_threads_only_own(client: AsyncClient):
    token_a = await _login(client, "a@example.com", "usera")
    client.headers.update({"Authorization": f"Bearer {token_a}"})
    await client.post("/api/threads", json={"title": "A's thread"})

    token_b = await _login(client, "b@example.com", "userb")
    client.headers.update({"Authorization": f"Bearer {token_b}"})
    await client.post("/api/threads", json={"title": "B's thread"})

    resp = await client.get("/api/threads")
    assert resp.status_code == status.HTTP_200_OK
    titles = {t["title"] for t in resp.json()}
    assert titles == {"B's thread"}


async def test_get_thread(auth_client: AsyncClient):
    create_resp = await auth_client.post("/api/threads", json={"title": "Mine"})
    thread_id = create_resp.json()["id"]
    resp = await auth_client.get(f"/api/threads/{thread_id}")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["title"] == "Mine"


async def test_get_thread_not_found(auth_client: AsyncClient):
    resp = await auth_client.get("/api/threads/999999")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_get_thread_not_owned(client: AsyncClient):
    token_a = await _login(client, "a@example.com", "usera")
    client.headers.update({"Authorization": f"Bearer {token_a}"})
    create_resp = await client.post("/api/threads", json={"title": "A's thread"})
    thread_id = create_resp.json()["id"]

    token_b = await _login(client, "b@example.com", "userb")
    client.headers.update({"Authorization": f"Bearer {token_b}"})
    resp = await client.get(f"/api/threads/{thread_id}")
    assert resp.status_code == status.HTTP_403_FORBIDDEN


async def test_rename_thread(auth_client: AsyncClient):
    create_resp = await auth_client.post("/api/threads", json={"title": "Old"})
    thread_id = create_resp.json()["id"]
    resp = await auth_client.patch(f"/api/threads/{thread_id}", json={"title": "New"})
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["title"] == "New"


async def test_rename_thread_not_found(auth_client: AsyncClient):
    resp = await auth_client.patch("/api/threads/999999", json={"title": "New"})
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_rename_thread_not_owned(client: AsyncClient):
    token_a = await _login(client, "a@example.com", "usera")
    client.headers.update({"Authorization": f"Bearer {token_a}"})
    create_resp = await client.post("/api/threads", json={"title": "A's thread"})
    thread_id = create_resp.json()["id"]

    token_b = await _login(client, "b@example.com", "userb")
    client.headers.update({"Authorization": f"Bearer {token_b}"})
    resp = await client.patch(f"/api/threads/{thread_id}", json={"title": "Hijacked"})
    assert resp.status_code == status.HTTP_403_FORBIDDEN


async def test_delete_thread(auth_client: AsyncClient):
    create_resp = await auth_client.post("/api/threads", json={"title": "Doomed"})
    thread_id = create_resp.json()["id"]
    resp = await auth_client.delete(f"/api/threads/{thread_id}")
    assert resp.status_code == status.HTTP_200_OK

    get_resp = await auth_client.get(f"/api/threads/{thread_id}")
    assert get_resp.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_thread_not_found(auth_client: AsyncClient):
    resp = await auth_client.delete("/api/threads/999999")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


async def test_delete_thread_not_owned(client: AsyncClient):
    token_a = await _login(client, "a@example.com", "usera")
    client.headers.update({"Authorization": f"Bearer {token_a}"})
    create_resp = await client.post("/api/threads", json={"title": "A's thread"})
    thread_id = create_resp.json()["id"]

    token_b = await _login(client, "b@example.com", "userb")
    client.headers.update({"Authorization": f"Bearer {token_b}"})
    resp = await client.delete(f"/api/threads/{thread_id}")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # confirm the thread survives — owner can still see it
    client.headers.update({"Authorization": f"Bearer {token_a}"})
    get_resp = await client.get(f"/api/threads/{thread_id}")
    assert get_resp.status_code == status.HTTP_200_OK
