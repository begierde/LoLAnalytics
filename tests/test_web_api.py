from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from loltimecheck.core.config import AppConfig
from loltimecheck.web.app import create_app


def make_config(tmp: str) -> AppConfig:
    return AppConfig.for_sqlite(str(Path(tmp) / "api.sqlite"), admin_password="admin", jwt_secret="test-secret-that-is-long-enough-for-hs256")


def login(client: TestClient) -> dict:
    response = client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_auth_required_for_api() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with TestClient(create_app(make_config(tmp))) as client:
            assert client.get("/api/v1/health").status_code == 200
            assert client.get("/api/v1/settings").status_code == 401


def test_stats_api_returns_empty_shape() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with TestClient(create_app(make_config(tmp))) as client:
            headers = login(client)
            response = client.get("/api/v1/stats?days=30&timezone=UTC%2B08:00", headers=headers)
            assert response.status_code == 200
            body = response.json()
            assert body["summary"]["total_events"] == 0
            assert body["summary"]["heatmap"][0] == [0] * 24
            assert body["coverage"]["sampleQuality"] == "empty"
            assert body["coverage"]["latestSampleLocal"] is None
            assert body["dailyTrend"] == []
            assert len(body["weekdayAverages"]) == 7


def test_stats_api_accepts_half_hour_utc_offset() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with TestClient(create_app(make_config(tmp))) as client:
            headers = login(client)
            response = client.get("/api/v1/stats?days=30&timezone=UTC%2B05%3A30", headers=headers)
            assert response.status_code == 200
            assert response.json()["timezone"] == "UTC+05:30"


def test_stats_api_rejects_iana_timezone() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with TestClient(create_app(make_config(tmp))) as client:
            headers = login(client)
            response = client.get("/api/v1/stats?days=30&timezone=Asia/Shanghai", headers=headers)
            assert response.status_code == 400
            assert "unsupported timezone" in response.json()["detail"]


def test_settings_api_returns_timezones() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with TestClient(create_app(make_config(tmp))) as client:
            headers = login(client)
            body = client.get("/api/v1/settings", headers=headers).json()
            timezones = body["timezones"]
            values = {item["value"] for item in timezones}
            assert {"UTC", "UTC+08:00", "UTC+05:30", "UTC+05:45", "UTC+09:30", "UTC+12:45", "UTC+14:00", "UTC-12:00"} <= values
            assert all(set(item) == {"value", "country"} and item["country"] for item in timezones)


def test_settings_api_validates_template() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with TestClient(create_app(make_config(tmp))) as client:
            headers = login(client)
            response = client.put(
                "/api/v1/settings",
                headers=headers,
                json={
                    "monitorIntervalMinutes": 15,
                    "webhookUrl": "",
                    "webhookTemplate": '{"text":"$riot_id"}',
                },
            )
            assert response.status_code == 200
