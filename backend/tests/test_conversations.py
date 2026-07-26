async def _register_and_login(client, email: str) -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "TestPass123!", "full_name": "Test User"},
    )
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "TestPass123!"})
    return login.json()["access_token"]


async def test_conversations_require_authentication(client):
    response = await client.get("/api/v1/conversations")
    assert response.status_code == 401


async def test_create_and_list_conversation(client):
    token = await _register_and_login(client, "user1@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create = await client.post("/api/v1/conversations", json={}, headers=headers)
    assert create.status_code == 201
    conversation_id = create.json()["id"]

    listing = await client.get("/api/v1/conversations", headers=headers)
    assert listing.status_code == 200
    ids = [c["id"] for c in listing.json()]
    assert conversation_id in ids


async def test_get_conversation_detail(client):
    token = await _register_and_login(client, "user2@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create = await client.post("/api/v1/conversations", json={}, headers=headers)
    conversation_id = create.json()["id"]

    detail = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["messages"] == []


async def test_delete_conversation(client):
    token = await _register_and_login(client, "user3@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create = await client.post("/api/v1/conversations", json={}, headers=headers)
    conversation_id = create.json()["id"]

    delete = await client.delete(f"/api/v1/conversations/{conversation_id}", headers=headers)
    assert delete.status_code == 204

    get_after_delete = await client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    assert get_after_delete.status_code == 404


async def test_cannot_access_another_users_conversation(client):
    token_a = await _register_and_login(client, "owner@example.com")
    token_b = await _register_and_login(client, "intruder@example.com")

    create = await client.post(
        "/api/v1/conversations", json={}, headers={"Authorization": f"Bearer {token_a}"}
    )
    conversation_id = create.json()["id"]

    # Ownership-scoped lookups return 404, not 403 - matches this project's pattern throughout
    # (get_for_user-style repository queries filter by user_id in the WHERE clause, so a
    # mismatched owner looks identical to "doesn't exist" rather than leaking that the resource
    # exists at all).
    response = await client.get(
        f"/api/v1/conversations/{conversation_id}", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert response.status_code == 404


async def test_update_conversation_title(client):
    token = await _register_and_login(client, "user4@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    create = await client.post("/api/v1/conversations", json={}, headers=headers)
    conversation_id = create.json()["id"]

    update = await client.patch(
        f"/api/v1/conversations/{conversation_id}", json={"title": "Renamed"}, headers=headers
    )
    assert update.status_code == 200
    assert update.json()["title"] == "Renamed"
