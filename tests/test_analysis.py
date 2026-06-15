from __future__ import annotations

import unittest
from datetime import UTC, datetime

from loltimecheck.analysis import (
    FLEX_QUEUE_ID,
    compute_window,
    extract_flex_event,
    local_bucket,
    normalize_riot_id,
)


class AnalysisTests(unittest.TestCase):
    def test_compute_window_uses_days(self) -> None:
        now = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)
        window = compute_window(30, now)
        self.assertEqual(window.end_utc, now)
        self.assertEqual((window.end_utc - window.start_utc).days, 30)

    def test_extract_flex_event_filters_queue(self) -> None:
        match = {
            "metadata": {"matchId": "JP1_1", "participants": ["p1"]},
            "info": {"queueId": 420, "gameStartTimestamp": 1_780_000_000_000},
        }
        self.assertIsNone(extract_flex_event(match, "p1", "UTC+08:00"))

    def test_extract_flex_event_accepts_flex_queue(self) -> None:
        start_ms = int(datetime(2026, 6, 13, 8, 0, tzinfo=UTC).timestamp() * 1000)
        match = {
            "metadata": {"matchId": "JP1_1", "participants": ["p1"]},
            "info": {"queueId": FLEX_QUEUE_ID, "gameStartTimestamp": start_ms},
        }
        event = extract_flex_event(match, "p1", "UTC+08:00")
        self.assertIsNotNone(event)
        self.assertEqual(event["hour"], 16)

    def test_fixed_utc_offsets_are_supported(self) -> None:
        start_ms = int(datetime(2026, 6, 13, 8, 0, tzinfo=UTC).timestamp() * 1000)
        self.assertEqual(local_bucket(start_ms, "UTC+08:00")[1], 16)
        self.assertEqual(local_bucket(start_ms, "UTC-05:00")[1], 3)
        self.assertEqual(local_bucket(start_ms, "UTC+05:30")[1], 13)

    def test_iana_timezone_names_are_rejected(self) -> None:
        start_ms = int(datetime(2026, 6, 13, 8, 0, tzinfo=UTC).timestamp() * 1000)
        with self.assertRaisesRegex(ValueError, "unsupported timezone"):
            local_bucket(start_ms, "Asia/Shanghai")

    def test_invalid_utc_offset_is_rejected(self) -> None:
        start_ms = int(datetime(2026, 6, 13, 8, 0, tzinfo=UTC).timestamp() * 1000)
        with self.assertRaisesRegex(ValueError, "invalid UTC offset"):
            local_bucket(start_ms, "UTC+08:99")

    def test_riot_id_fallback(self) -> None:
        self.assertEqual(normalize_riot_id("abc", "JP1", "p" * 12), "abc#JP1")
        self.assertEqual(normalize_riot_id(None, None, "abcdef123456"), "PUUID:abcdef12")


if __name__ == "__main__":
    unittest.main()
