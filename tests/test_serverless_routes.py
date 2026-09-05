import pytest
from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)


def test_dashboard_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "FOOTBALL DESK" in response.text


def test_telegram_webhook_endpoint():
    dummy_update = {
        "update_id": 999999,
        "message": {
            "message_id": 1,
            "text": "/status",
            "chat": {"id": 12345678}
        }
    }
    response = client.post("/api/telegram/webhook", json=dummy_update)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_vercel_cron_poll_endpoint():
    response = client.get("/api/cron/poll")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "cron_success"
    assert "timestamp" in data
