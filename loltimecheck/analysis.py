from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

FLEX_QUEUE_ID = 440
WEEKDAYS_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
UTC_OFFSET_RE = re.compile(r"^UTC([+-])(\d{2}):(\d{2})$")


@dataclass(frozen=True)
class TimeWindow:
    start_utc: datetime
    end_utc: datetime

    @property
    def start_epoch(self) -> int:
        return int(self.start_utc.timestamp())

    @property
    def end_epoch(self) -> int:
        return int(self.end_utc.timestamp())

    @property
    def start_ms(self) -> int:
        return self.start_epoch * 1000

    @property
    def end_ms(self) -> int:
        return self.end_epoch * 1000


def compute_window(days: int, now_utc: datetime | None = None) -> TimeWindow:
    if days <= 0:
        raise ValueError("--days must be positive")
    end = now_utc or datetime.now(UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    end = end.astimezone(UTC)
    start = end - timedelta(days=days)
    return TimeWindow(start_utc=start, end_utc=end)


def normalize_riot_id(game_name: str | None, tag_line: str | None, puuid: str) -> str:
    if game_name and tag_line:
        return f"{game_name}#{tag_line}"
    if game_name:
        return game_name
    return f"PUUID:{puuid[:8]}"


def parse_timezone(timezone_name: str) -> timezone:
    if timezone_name == "UTC":
        return UTC
    match = UTC_OFFSET_RE.match(timezone_name)
    if match:
        sign, hours_raw, minutes_raw = match.groups()
        hours = int(hours_raw)
        minutes = int(minutes_raw)
        if minutes >= 60:
            raise ValueError(f"invalid UTC offset timezone: {timezone_name!r}")
        total_minutes = hours * 60 + minutes
        if sign == "-":
            total_minutes = -total_minutes
        if total_minutes < -12 * 60 or total_minutes > 14 * 60:
            raise ValueError(f"UTC offset timezone out of supported range: {timezone_name!r}")
        return timezone(timedelta(minutes=total_minutes), timezone_name)
    raise ValueError(
        f"unsupported timezone: {timezone_name!r}. "
        "Use UTC or a fixed offset like UTC+08:00."
    )


def local_bucket(game_start_ms: int, timezone: str) -> tuple[str, int, datetime]:
    tz = parse_timezone(timezone)
    local_dt = datetime.fromtimestamp(game_start_ms / 1000, UTC).astimezone(tz)
    return WEEKDAYS_CN[local_dt.weekday()], local_dt.hour, local_dt


def extract_flex_event(match: dict, puuid: str, timezone: str) -> dict | None:
    info = match.get("info") or {}
    metadata = match.get("metadata") or {}
    if info.get("queueId") != FLEX_QUEUE_ID:
        return None
    participant_puuids = set(metadata.get("participants") or [])
    if participant_puuids and puuid not in participant_puuids:
        return None
    start_ms = info.get("gameStartTimestamp")
    if not isinstance(start_ms, int):
        return None
    weekday, hour, local_dt = local_bucket(start_ms, timezone)
    return {
        "match_id": metadata.get("matchId") or "",
        "puuid": puuid,
        "game_start_ms": start_ms,
        "local_datetime": local_dt.isoformat(),
        "weekday": weekday,
        "weekday_index": local_dt.weekday(),
        "hour": hour,
        "duration_seconds": info.get("gameDuration"),
    }


def summarize_events(events: list[dict]) -> dict:
    heatmap = [[0 for _ in range(24)] for _ in range(7)]
    hour_counter: Counter[int] = Counter()
    weekday_counter: Counter[int] = Counter()
    player_counter: Counter[str] = Counter()
    player_hours: dict[str, Counter[int]] = defaultdict(Counter)

    for event in events:
        weekday_index = int(event["weekday_index"])
        hour = int(event["hour"])
        puuid = str(event["puuid"])
        heatmap[weekday_index][hour] += 1
        hour_counter[hour] += 1
        weekday_counter[weekday_index] += 1
        player_counter[puuid] += 1
        player_hours[puuid][hour] += 1

    top_slots = []
    for weekday_index in range(7):
        for hour in range(24):
            count = heatmap[weekday_index][hour]
            if count:
                top_slots.append(
                    {
                        "weekday": WEEKDAYS_CN[weekday_index],
                        "weekday_index": weekday_index,
                        "hour": hour,
                        "count": count,
                    }
                )
    top_slots.sort(key=lambda item: (-item["count"], item["weekday_index"], item["hour"]))

    weekend_count = weekday_counter[5] + weekday_counter[6]
    weekday_count = sum(weekday_counter[i] for i in range(5))

    return {
        "total_events": len(events),
        "unique_players": len(player_counter),
        "heatmap": heatmap,
        "hour_counts": dict(hour_counter),
        "weekday_counts": {WEEKDAYS_CN[i]: weekday_counter[i] for i in range(7)},
        "top_slots": top_slots[:10],
        "weekday_total": weekday_count,
        "weekend_total": weekend_count,
        "player_counts": dict(player_counter),
        "player_top_hours": {
            puuid: [hour for hour, _ in counter.most_common(3)]
            for puuid, counter in player_hours.items()
        },
    }
