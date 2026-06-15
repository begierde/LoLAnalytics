from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from loltimecheck.analysis import WEEKDAYS_CN, compute_window, extract_flex_event, parse_timezone, summarize_events
from loltimecheck.storage.repository import Store

EXCLUDED_CHART_HOURS = set(range(2, 11))


def player_map(store: Store) -> dict[str, dict]:
    return {
        row["puuid"]: {"riot_id": row["riot_id"], "league_points": row["league_points"]}
        for row in store.list_players()
    }


def events_from_store(store: Store, *, days: int, timezone: str) -> list[dict]:
    window = compute_window(days)
    events = []
    for row in store.iter_events(window.start_ms, window.end_ms):
        match = row["raw_json"]
        event = extract_flex_event(match, row["puuid"], timezone)
        if event:
            event["riot_id"] = row["riot_id"]
            event["league_points"] = row["league_points"]
            events.append(event)
    return events


def _chart_summary(events: list[dict]) -> dict:
    chart_events = [event for event in events if int(event["hour"]) not in EXCLUDED_CHART_HOURS]
    return summarize_events(chart_events)


def _event_datetime(event: dict) -> datetime:
    return datetime.fromisoformat(str(event["local_datetime"]))


def _daily_trend(events: list[dict]) -> list[dict]:
    counts: Counter[str] = Counter()
    weekdays: dict[str, int] = {}
    for event in events:
        local_dt = _event_datetime(event)
        key = local_dt.date().isoformat()
        counts[key] += 1
        weekdays[key] = local_dt.weekday()
    return [
        {
            "date": date,
            "count": counts[date],
            "weekday": WEEKDAYS_CN[weekdays[date]],
            "weekdayIndex": weekdays[date],
        }
        for date in sorted(counts)
    ]


def _weekday_averages(daily_trend: list[dict]) -> list[dict]:
    weekday_counts: dict[int, list[int]] = {index: [] for index in range(7)}
    for row in daily_trend:
        weekday_counts[int(row["weekdayIndex"])].append(int(row["count"]))
    result = []
    for index in range(7):
        counts = weekday_counts[index]
        total = sum(counts)
        result.append(
            {
                "weekday": WEEKDAYS_CN[index],
                "weekdayIndex": index,
                "days": len(counts),
                "total": total,
                "average": round(total / len(counts), 2) if counts else 0,
            }
        )
    return result


def _coverage(events: list[dict], *, days: int, timezone_name: str) -> dict:
    if not events:
        return {
            "requestedDays": days,
            "timezone": timezone_name,
            "firstSampleLocal": None,
            "latestSampleLocal": None,
            "coveredDays": 0,
            "dailyAverage": 0,
            "freshnessHours": None,
            "sampleQuality": "empty",
        }
    local_datetimes = [_event_datetime(event) for event in events]
    first_sample = min(local_datetimes)
    latest_sample = max(local_datetimes)
    covered_days = len({item.date().isoformat() for item in local_datetimes})
    freshness_hours = max(
        0,
        round((datetime.now(UTC) - latest_sample.astimezone(UTC)).total_seconds() / 3600, 1),
    )
    return {
        "requestedDays": days,
        "timezone": timezone_name,
        "firstSampleLocal": first_sample.isoformat(),
        "latestSampleLocal": latest_sample.isoformat(),
        "coveredDays": covered_days,
        "dailyAverage": round(len(events) / covered_days, 2) if covered_days else 0,
        "freshnessHours": freshness_hours,
        "sampleQuality": "low" if len(events) < 20 else "ok",
    }


def _recent_trend(daily_trend: list[dict]) -> dict:
    if not daily_trend:
        return {
            "recent7Total": 0,
            "previous7Total": 0,
            "delta": 0,
            "deltaPercent": None,
            "direction": "flat",
        }
    recent = daily_trend[-7:]
    previous = daily_trend[-14:-7]
    recent_total = sum(int(row["count"]) for row in recent)
    previous_total = sum(int(row["count"]) for row in previous)
    delta = recent_total - previous_total
    if previous_total:
        delta_percent = round(delta / previous_total * 100, 1)
    else:
        delta_percent = None
    if delta > 0:
        direction = "up"
    elif delta < 0:
        direction = "down"
    else:
        direction = "flat"
    return {
        "recent7Total": recent_total,
        "previous7Total": previous_total,
        "delta": delta,
        "deltaPercent": delta_percent,
        "direction": direction,
    }


def _insights(summary: dict, display_summary: dict, daily_trend: list[dict], weekday_averages: list[dict]) -> dict:
    hour_counts = {int(hour): count for hour, count in display_summary["hour_counts"].items()}
    peak_hour = None
    if hour_counts:
        hour, count = sorted(hour_counts.items(), key=lambda item: (-item[1], item[0]))[0]
        peak_hour = {"hour": hour, "count": count}

    recommended_slots = display_summary["top_slots"][:3]
    weekday_average = round(sum(item["average"] for item in weekday_averages[:5]) / 5, 2)
    weekend_days = [item for item in weekday_averages if item["weekdayIndex"] in {5, 6}]
    weekend_average = round(sum(item["average"] for item in weekend_days) / 2, 2)
    if weekend_average > weekday_average:
        weekend_direction = "higher"
    elif weekend_average < weekday_average:
        weekend_direction = "lower"
    else:
        weekend_direction = "flat"

    return {
        "peakHour": peak_hour,
        "recommendedSlots": recommended_slots,
        "weekdayDailyAverage": weekday_average,
        "weekendDailyAverage": weekend_average,
        "weekendDirection": weekend_direction,
        "recentTrend": _recent_trend(daily_trend),
        "sampleQuality": "low" if summary["total_events"] < 20 else "ok",
    }


def stats_payload(
    store: Store,
    *,
    days: int,
    timezone: str,
    player_page: int = 1,
    player_page_size: int = 10,
) -> dict:
    parse_timezone(timezone)
    events = events_from_store(store, days=days, timezone=timezone)
    players = player_map(store)
    summary = summarize_events(events)
    display_summary = _chart_summary(events)
    daily_trend = _daily_trend(events)
    weekday_averages = _weekday_averages(daily_trend)
    player_rows = []
    for puuid, count in summary["player_counts"].items():
        player = players.get(puuid, {})
        player_rows.append(
            {
                "puuid": puuid,
                "riotId": player.get("riot_id") or puuid[:8],
                "count": count,
                "topHours": summary["player_top_hours"].get(puuid, []),
                "leaguePoints": player.get("league_points"),
            }
        )
    player_rows.sort(
        key=lambda item: (
            -(item["leaguePoints"] if item["leaguePoints"] is not None else -1),
            item["riotId"].lower(),
        )
    )
    page = max(1, player_page)
    page_size = max(1, min(player_page_size, 200))
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "days": days,
        "timezone": timezone,
        "summary": summary,
        "displaySummary": display_summary,
        "coverage": _coverage(events, days=days, timezone_name=timezone),
        "insights": _insights(summary, display_summary, daily_trend, weekday_averages),
        "dailyTrend": daily_trend,
        "weekdayAverages": weekday_averages,
        "players": player_rows[start:end],
        "playerPagination": {
            "page": page,
            "pageSize": page_size,
            "total": len(player_rows),
            "totalPages": (len(player_rows) + page_size - 1) // page_size if player_rows else 0,
        },
        "chartExcludedHours": sorted(EXCLUDED_CHART_HOURS),
    }
