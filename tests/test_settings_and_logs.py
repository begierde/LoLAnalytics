from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from loltimecheck.core.config import AppConfig
from loltimecheck.core.constants import rank_scope_tiers, server_routes
from loltimecheck.services.jobs import CollectionWorker
from loltimecheck.storage.repository import Store
from loltimecheck.web.app import create_app


def make_config(tmp: str) -> AppConfig:
    return AppConfig.for_sqlite(str(Path(tmp) / "api.sqlite"), admin_password="admin", jwt_secret="test-secret-that-is-long-enough-for-hs256")


def login(client: TestClient) -> dict:
    response = client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_server_and_rank_scope_mapping() -> None:
    assert server_routes("JP")["platform"] == "jp1"
    assert server_routes("NA")["regional"] == "americas"
    assert rank_scope_tiers("challenger_grandmaster_master") == ["CHALLENGER", "GRANDMASTER", "MASTER"]


def test_settings_masks_riot_key_and_does_not_return_plaintext() -> None:
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
                    "language": "en",
                    "defaultServer": "NA",
                    "defaultRankScope": "challenger_grandmaster",
                    "riotApiKey": "RGAPI-1234567890abcdef",
                },
            )
            assert response.status_code == 200
            body = client.get("/api/v1/settings", headers=headers).json()
            assert body["language"] == "en"
            assert body["defaultServer"] == "NA"
            assert body["defaultRankScope"] == "challenger_grandmaster"
            assert body["hasRiotApiKey"] is True
            assert "1234567890abcdef" not in str(body)
            assert body["riotApiKeyMasked"].startswith("RGAPI-")


def test_collection_job_is_queued_and_worker_fails_without_key() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        config = make_config(tmp)
        with TestClient(create_app(config)) as client:
            headers = login(client)
            job_id = client.post(
                "/api/v1/collection-jobs",
                headers=headers,
                json={
                    "days": 30,
                    "timezone": "UTC+08:00",
                    "limitPlayers": 1,
                    "refreshLeague": False,
                    "server": "JP",
                    "rankScope": "challenger",
                },
            ).json()["jobId"]
            assert client.get(f"/api/v1/collection-jobs/{job_id}", headers=headers).json()["status"] == "pending"
        assert CollectionWorker(config).run_once() is True
        with TestClient(create_app(config)) as client:
            headers = login(client)
            job = client.get(f"/api/v1/collection-jobs/{job_id}", headers=headers).json()
            assert job["status"] == "failed"
            assert "Settings" in job["error"]


def test_logs_can_be_filtered_and_cleared() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        config = make_config(tmp)
        with Store(config.database_url) as store:
            store.init_schema()
            store.add_log(level="info", category="collection", message="one")
            store.add_log(level="error", category="api_key", message="two")
        with TestClient(create_app(config)) as client:
            headers = login(client)
            logs = client.get("/api/v1/logs?level=error", headers=headers).json()["logs"]
            assert len(logs) == 1
            assert logs[0]["category"] == "api_key"
            assert client.delete("/api/v1/logs", headers=headers).status_code == 200
            after = client.get("/api/v1/logs", headers=headers).json()["logs"]
            assert len(after) == 1
            assert after[0]["category"] == "logs"


def test_jobs_api_paginates_default_ten() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        config = make_config(tmp)
        with Store(config.database_url) as store:
            store.init_schema()
            for index in range(12):
                store.create_job(
                    days=30,
                    timezone="UTC+08:00",
                    limit_players=index + 1,
                    refresh_league=False,
                    server="JP",
                    rank_scope="challenger",
                )
        with TestClient(create_app(config)) as client:
            headers = login(client)
            first = client.get("/api/v1/collection-jobs", headers=headers).json()
            second = client.get("/api/v1/collection-jobs?page=2&pageSize=10", headers=headers).json()
            assert len(first["jobs"]) == 10
            assert first["pagination"]["total"] == 12
            assert first["pagination"]["totalPages"] == 2
            assert len(second["jobs"]) == 2


def test_stats_players_page_by_lp_and_chart_excludes_early_hours() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        config = make_config(tmp)
        now_ms = int(datetime(2026, 6, 13, 12, 0, tzinfo=UTC).timestamp() * 1000)
        early_ms = int(datetime(2026, 6, 13, 2, 0, tzinfo=UTC).timestamp() * 1000)
        with Store(config.database_url) as store:
            store.init_schema()
            for idx, lp in enumerate([10, 50, 30], start=1):
                puuid = f"p{idx}"
                store.upsert_player(
                    puuid=puuid,
                    riot_id=f"player{idx}#JP1",
                    game_name=f"player{idx}",
                    tag_line="JP1",
                    summoner_id=f"s{idx}",
                    league_points=lp,
                    wins=1,
                    losses=1,
                )
                match = {"metadata": {"matchId": f"JP1_{idx}", "participants": [puuid]}, "info": {"queueId": 440, "gameStartTimestamp": now_ms}}
                store.upsert_match(f"JP1_{idx}", match)
                store.link_player_match(puuid, f"JP1_{idx}")
            early_match = {"metadata": {"matchId": "JP1_early", "participants": ["p1"]}, "info": {"queueId": 440, "gameStartTimestamp": early_ms}}
            store.upsert_match("JP1_early", early_match)
            store.link_player_match("p1", "JP1_early")
        with TestClient(create_app(config)) as client:
            headers = login(client)
            body = client.get("/api/v1/stats?days=365&timezone=UTC&playerPage=1&playerPageSize=2", headers=headers).json()
            assert body["players"][0]["riotId"] == "player2#JP1"
            assert body["players"][1]["riotId"] == "player3#JP1"
            assert body["playerPagination"]["total"] == 3
            assert body["displaySummary"]["hour_counts"].get("2") is None
            assert 2 in body["chartExcludedHours"]
