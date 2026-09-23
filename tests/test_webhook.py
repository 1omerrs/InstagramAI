import hashlib
import hmac
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.memory import init_db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("VERIFY_TOKEN", "test-token")
    monkeypatch.setenv("META_APP_SECRET", "")
    monkeypatch.setenv("IG_ACCESS_TOKEN", "")
    monkeypatch.setenv("IG_USER_ID", "")
    monkeypatch.setenv("N8N_WEBHOOK_URL", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    init_db()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def _payload(text="Merhaba", mid="m-1", echo=False):
    message = {"mid": mid, "text": text}
    if echo:
        message["is_echo"] = True
    return {
        "object": "instagram",
        "entry": [
            {
                "id": "ig-account",
                "messaging": [
                    {
                        "sender": {"id": "customer-1"},
                        "recipient": {"id": "ig-account"},
                        "timestamp": 1710000000,
                        "message": message,
                    }
                ],
            }
        ],
    }


def test_webhook_verification(client):
    ok = client.get(
        "/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "test-token", "hub.challenge": "12345"},
    )
    assert ok.status_code == 200
    assert ok.text == "12345"

    denied = client.get(
        "/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "12345"},
    )
    assert denied.status_code == 403


def test_inbound_message_stores_fallback_reply(client):
    response = client.post("/webhook", json=_payload())
    assert response.status_code == 200
    assert response.json()["accepted"] == 1

    history = client.get("/v1/conversations/customer-1")
    roles = [item["role"] for item in history.json()["messages"]]
    assert roles == ["user", "assistant"]
    assert "test yanıtı" in history.json()["messages"][1]["content"]


def test_echo_and_duplicate_are_ignored(client):
    echo = client.post("/webhook", json=_payload(echo=True, mid="echo-1"))
    assert echo.json()["accepted"] == 0

    first = client.post("/webhook", json=_payload(mid="same"))
    second = client.post("/webhook", json=_payload(mid="same"))
    assert first.json()["accepted"] == 1
    assert second.json()["accepted"] == 1

    history = client.get("/v1/conversations/customer-1")
    assert len(history.json()["messages"]) == 2


def test_invalid_signature_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("VERIFY_TOKEN", "test-token")
    monkeypatch.setenv("META_APP_SECRET", "secret")
    monkeypatch.setenv("N8N_WEBHOOK_URL", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    init_db()
    from app.main import app

    with TestClient(app) as client:
        denied = client.post("/webhook", json=_payload(), headers={"X-Hub-Signature-256": "sha256=dead"})
        assert denied.status_code == 403

        body = b'{"object":"instagram","entry":[]}'
        digest = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        allowed = client.post(
            "/webhook",
            content=body,
            headers={"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={digest}"},
        )
        assert allowed.status_code == 200
    get_settings.cache_clear()


def test_n8n_forward_does_not_reply_locally(client, monkeypatch):
    monkeypatch.setenv("N8N_WEBHOOK_URL", "http://n8n.local/webhook/instagram-inbound")
    get_settings.cache_clear()

    with patch("app.dispatch.post_json", new_callable=AsyncMock) as post_json:
        response = client.post("/webhook", json=_payload(mid="n8n-1"))

    assert response.status_code == 200
    post_json.assert_awaited_once()
    forwarded = post_json.await_args.args[1]
    assert forwarded["sender_id"] == "customer-1"
    assert forwarded["text"] == "Merhaba"
    history = client.get("/v1/conversations/customer-1")
    assert history.json()["messages"] == []


def test_reply_endpoint_uses_fallback_without_api_key(client):
    response = client.post("/v1/reply", json={"sender_id": "customer-9", "text": "Fiyat nedir?"})
    assert response.status_code == 200
    assert "test yanıtı" in response.json()["reply"]


def test_send_without_token_returns_503(client):
    response = client.post("/v1/send", json={"recipient_id": "customer-1", "text": "Selam"})
    assert response.status_code == 503
    assert response.json()["delivered"] is False
