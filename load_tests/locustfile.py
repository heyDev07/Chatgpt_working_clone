"""Load test for the app's own request-handling path - deliberately does NOT hammer real chat
completions. Every configured LLM provider has a real rate limit (OpenRouter's free daily quota,
Gemini's per-minute/day quota - both hit repeatedly over the course of building this project),
so concurrent virtual users all sending real chat messages would measure the *provider's* rate
limiter kicking in, not this app's own capacity under load. What's actually under test here -
auth, conversation CRUD, tool listing - exercises the same DB/Redis/FastAPI path a real chat
request does, just without the part that costs real API quota per request.

Run: locust -f load_tests/locustfile.py --host http://localhost:8000
Needs load_tests/seed_users.py run first, once, against the same backend.
"""

import random

from locust import HttpUser, between, task

USER_COUNT = 20
PASSWORD = "LoadTest123!"


class ChatAppUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        email = f"loadtest-{random.randint(0, USER_COUNT - 1)}@example.com"
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": PASSWORD},
            name="/api/v1/auth/login",
        )
        token = response.json().get("access_token") if response.status_code == 200 else None
        if token:
            self.client.headers.update({"Authorization": f"Bearer {token}"})
        self.conversation_ids: list[str] = []

    @task(5)
    def list_conversations(self):
        self.client.get("/api/v1/conversations", name="/api/v1/conversations [list]")

    @task(3)
    def create_conversation(self):
        response = self.client.post("/api/v1/conversations", json={}, name="/api/v1/conversations [create]")
        if response.status_code == 201:
            self.conversation_ids.append(response.json()["id"])

    @task(2)
    def get_conversation(self):
        if not self.conversation_ids:
            return
        conv_id = random.choice(self.conversation_ids)
        self.client.get(f"/api/v1/conversations/{conv_id}", name="/api/v1/conversations/[id]")

    @task(1)
    def delete_conversation(self):
        if not self.conversation_ids:
            return
        conv_id = self.conversation_ids.pop()
        self.client.delete(f"/api/v1/conversations/{conv_id}", name="/api/v1/conversations/[id] [delete]")

    @task(2)
    def list_tools(self):
        self.client.get("/api/v1/tools", name="/api/v1/tools")

    @task(2)
    def me(self):
        self.client.get("/api/v1/auth/me", name="/api/v1/auth/me")
