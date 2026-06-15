from __future__ import annotations

import tempfile
from pathlib import Path

from loltimecheck.services.monitoring import check_monitors, parse_riot_id
from loltimecheck.storage.repository import Store


class FakeRiotClient:
    def get_current_game_by_puuid(self, puuid: str) -> dict:
        return {
            "gameId": 12345,
            "gameQueueConfigId": 440,
            "gameStartTime": 1_780_000_000_000,
        }


def test_parse_riot_id_requires_tagline() -> None:
    assert parse_riot_id("abc#JP1") == ("abc", "JP1")
    try:
        parse_riot_id("abc")
    except ValueError as exc:
        assert "gameName#tagLine" in str(exc)
    else:
        raise AssertionError("parse_riot_id should reject missing tagLine")


def test_monitor_notification_dedupes_same_game(monkeypatch) -> None:
    calls = []

    def fake_post(url, payload):
        calls.append((url, payload))
        return 200, "ok"

    monkeypatch.setattr("loltimecheck.services.monitoring.post_json", fake_post)
    with tempfile.TemporaryDirectory() as tmp:
        with Store(Path(tmp) / "test.sqlite") as store:
            store.init_schema()
            store.update_settings(
                {
                    "webhook_url": "https://example.test/webhook",
                    "webhook_template": '{"riot_id":"$riot_id","game_id":"$game_id"}',
                }
            )
            store.upsert_monitor(
                puuid="p1",
                riot_id="abc#JP1",
                game_name="abc",
                tag_line="JP1",
            )
            first = check_monitors(store, FakeRiotClient())
            second = check_monitors(store, FakeRiotClient())
            assert first.notifications == 1
            assert second.notifications == 0
            assert len(calls) == 1

