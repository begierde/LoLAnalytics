from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from loltimecheck.analysis import FLEX_QUEUE_ID
from loltimecheck.storage.repository import Store


class StoreTests(unittest.TestCase):
    def test_match_cache_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cache.sqlite"
            match = {
                "metadata": {"matchId": "JP1_1", "participants": ["p1"]},
                "info": {"queueId": FLEX_QUEUE_ID, "gameStartTimestamp": 1_780_000_000_000},
            }
            with Store(db_path) as store:
                store.init_schema()
                store.upsert_player(
                    puuid="p1",
                    riot_id="name#JP1",
                    game_name="name",
                    tag_line="JP1",
                    summoner_id="s1",
                    league_points=1000,
                    wins=10,
                    losses=1,
                )
                store.upsert_match("JP1_1", match)
                store.upsert_match("JP1_1", match)
                store.link_player_match("p1", "JP1_1")
                store.link_player_match("p1", "JP1_1")
                events = list(store.iter_events(1_700_000_000_000, 1_800_000_000_000))
                self.assertEqual(len(events), 1)

    def test_retention_deletes_old_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cache.sqlite"
            old_match = {
                "metadata": {"matchId": "JP1_old", "participants": ["p1"]},
                "info": {"queueId": FLEX_QUEUE_ID, "gameStartTimestamp": 1},
            }
            with Store(db_path) as store:
                store.init_schema()
                store.upsert_player(
                    puuid="p1",
                    riot_id="name#JP1",
                    game_name="name",
                    tag_line="JP1",
                    summoner_id="s1",
                    league_points=1000,
                    wins=10,
                    losses=1,
                )
                store.upsert_match("JP1_old", old_match)
                store.link_player_match("p1", "JP1_old")
                store.purge_older_than(365)
                self.assertEqual(list(store.iter_events(0, 2)), [])


if __name__ == "__main__":
    unittest.main()
