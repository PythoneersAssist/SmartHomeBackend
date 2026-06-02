"""Tests for the non-AI Gemini endpoints (/api/gemini/*).

The websocket chat endpoint requires the external Groq model and is not covered
here. These tests exercise the endpoints that work without any model call:
status diagnostics and the in-memory chat-history read/clear endpoints.
"""

from tests.conftest import auth_header, create_user_and_login


class TestGeminiStatus:

    def test_status_returns_diagnostics(self, client):
        resp = client.get("/api/gemini/status")
        assert resp.status_code == 200
        body = resp.json()
        # Diagnostic shape should always be present regardless of key config.
        assert "groq_key_present" in body
        assert "initialized" in body
        assert isinstance(body["groq_key_present"], bool)
        assert isinstance(body["initialized"], bool)


class TestGeminiHistory:

    def test_history_empty_for_new_user(self, client):
        _, token = create_user_and_login(client)
        resp = client.get(f"/api/gemini/history?token={token}")
        assert resp.status_code == 200
        assert resp.json()["messages"] == []

    def test_history_requires_token_param(self, client):
        # token is a required query parameter.
        resp = client.get("/api/gemini/history")
        assert resp.status_code == 422

    def test_clear_history_succeeds(self, client):
        _, token = create_user_and_login(client)
        resp = client.post(f"/api/gemini/clear-history?token={token}")
        assert resp.status_code == 200
        assert "cleared" in resp.json()["message"].lower()

    def test_clear_history_requires_token_param(self, client):
        resp = client.post("/api/gemini/clear-history")
        assert resp.status_code == 422

    def test_history_after_clear_is_empty(self, client):
        _, token = create_user_and_login(client)
        client.post(f"/api/gemini/clear-history?token={token}")
        resp = client.get(f"/api/gemini/history?token={token}")
        assert resp.status_code == 200
        assert resp.json()["messages"] == []
