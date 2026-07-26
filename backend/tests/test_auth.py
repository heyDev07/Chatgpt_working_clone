async def test_register_returns_user(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "TestPass123!", "full_name": "Alice"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert "password" not in body and "password_hash" not in body


async def test_register_duplicate_email_rejected(client):
    payload = {"email": "bob@example.com", "password": "TestPass123!", "full_name": "Bob"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 422


async def test_login_with_correct_password_succeeds(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "carol@example.com", "password": "TestPass123!", "full_name": "Carol"},
    )
    response = await client.post(
        "/api/v1/auth/login", json={"email": "carol@example.com", "password": "TestPass123!"}
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_login_with_wrong_password_rejected(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "dave@example.com", "password": "TestPass123!", "full_name": "Dave"},
    )
    response = await client.post(
        "/api/v1/auth/login", json={"email": "dave@example.com", "password": "WrongPassword!"}
    )
    assert response.status_code == 401


async def test_login_nonexistent_user_rejected(client):
    response = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )
    assert response.status_code == 401


async def test_me_requires_authentication(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user(client):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "erin@example.com", "password": "TestPass123!", "full_name": "Erin"},
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": "erin@example.com", "password": "TestPass123!"}
    )
    token = login.json()["access_token"]

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "erin@example.com"


async def test_register_rate_limited_after_five_per_ip(client):
    # Phase 15's register_rate_limiter: 5 requests per 5 minutes per IP. httpx's ASGITransport
    # has no real client IP, so every request in this test shares whatever the app resolves as
    # the identifier - exactly what makes this the right test for "does the limiter actually
    # trigger", regardless of what that shared identifier happens to be.
    for i in range(5):
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": f"ratelimit{i}@example.com", "password": "TestPass123!", "full_name": "Test"},
        )
        assert response.status_code == 201

    sixth = await client.post(
        "/api/v1/auth/register",
        json={"email": "ratelimit-sixth@example.com", "password": "TestPass123!", "full_name": "Test"},
    )
    assert sixth.status_code == 429
