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


def test_auth_verify_endpoint():
    # Invalid PIN
    bad_res = client.post("/api/auth/verify", json={"pin": "wrong999"})
    assert bad_res.status_code == 401
    assert bad_res.json()["detail"] == "Invalid Security PIN"

    # Valid PIN
    good_res = client.post("/api/auth/verify", json={"pin": "2026"})
    assert good_res.status_code == 200
    assert good_res.json() == {"valid": True, "message": "Authentication successful"}


def test_protected_routes_require_valid_pin():
    # 1. Matches Configure
    unauth = client.post("/api/matches/configure", json={"match_id": "test_m1", "tracked": True})
    assert unauth.status_code == 401
    assert "Valid Desk Security PIN required" in unauth.json()["detail"]

    bad_pin = client.post(
        "/api/matches/configure",
        json={"match_id": "test_m1", "tracked": True},
        headers={"X-Desk-PIN": "0000"}
    )
    assert bad_pin.status_code == 401

    auth = client.post(
        "/api/matches/configure",
        json={"match_id": "sched_101", "tracked": True, "coverage": "STANDARD", "auto_publish": True, "language": "bn"},
        headers={"X-Desk-PIN": "2026"}
    )
    assert auth.status_code == 200
    assert auth.json()["status"] == "tracked"

    # 2. Night Shift start/stop
    ns_unauth = client.post("/api/nightshift/start")
    assert ns_unauth.status_code == 401

    ns_auth = client.post("/api/nightshift/start", headers={"X-Desk-PIN": "2026"})
    assert ns_auth.status_code == 200
    assert ns_auth.json()["status"] == "night_shift_armed"

    # 3. Settings update
    set_unauth = client.post("/api/settings/coverage", json={"default_language": "en"})
    assert set_unauth.status_code == 401

    set_auth = client.post(
        "/api/settings/coverage",
        json={"default_language": "en"},
        headers={"X-Desk-PIN": "2026"}
    )
    assert set_auth.status_code == 200
    assert set_auth.json()["default_language"] == "en"

