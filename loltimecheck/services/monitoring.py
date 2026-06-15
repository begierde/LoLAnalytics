from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from loltimecheck.analysis import FLEX_QUEUE_ID, normalize_riot_id
from loltimecheck.integrations.riot import CurrentGameNotFound, RiotClient
from loltimecheck.integrations.webhook import post_json, render_template
from loltimecheck.storage.repository import Store


@dataclass
class MonitorResult:
    checked: int = 0
    in_flex: int = 0
    notifications: int = 0


def parse_riot_id(riot_id: str) -> tuple[str, str]:
    if "#" not in riot_id:
        raise ValueError("Riot ID must use gameName#tagLine format")
    game_name, tag_line = riot_id.rsplit("#", 1)
    game_name = game_name.strip()
    tag_line = tag_line.strip()
    if not game_name or not tag_line:
        raise ValueError("Riot ID must include both gameName and tagLine")
    return game_name, tag_line


def add_monitor(store: Store, client: RiotClient, riot_id: str) -> int:
    game_name, tag_line = parse_riot_id(riot_id)
    account = client.get_account_by_riot_id(game_name, tag_line)
    puuid = account.get("puuid")
    if not puuid:
        raise ValueError("Riot ID validation did not return PUUID")
    canonical = normalize_riot_id(account.get("gameName") or game_name, account.get("tagLine") or tag_line, puuid)
    return store.upsert_monitor(
        puuid=puuid,
        riot_id=canonical,
        game_name=account.get("gameName") or game_name,
        tag_line=account.get("tagLine") or tag_line,
    )


def _game_started_at(game: dict) -> str:
    start_ms = game.get("gameStartTime")
    if isinstance(start_ms, int):
        return datetime.fromtimestamp(start_ms / 1000, UTC).isoformat()
    return ""


def check_monitors(store: Store, client: RiotClient) -> MonitorResult:
    settings = store.get_settings()
    webhook_url = settings.get("webhook_url", "").strip()
    webhook_template = settings.get("webhook_template", "{}")
    result = MonitorResult()
    checked_at = datetime.now(UTC).isoformat()
    for monitor in store.list_monitors(enabled_only=True):
        result.checked += 1
        try:
            game = client.get_current_game_by_puuid(monitor["puuid"])
        except CurrentGameNotFound:
            store.record_monitor_check(monitor_id=monitor["id"], status="not_in_game")
            store.add_log(
                level="debug",
                category="monitor",
                message=f"{monitor['riot_id']} is not in game",
                object_type="monitor",
                object_id=monitor["id"],
            )
            continue
        queue_id = game.get("gameQueueConfigId")
        game_id = str(game.get("gameId") or "")
        if queue_id != FLEX_QUEUE_ID:
            store.record_monitor_check(
                monitor_id=monitor["id"],
                status="in_other_queue",
                game_id=game_id,
                queue_id=queue_id,
            )
            store.add_log(
                level="debug",
                category="monitor",
                message=f"{monitor['riot_id']} is in another queue",
                object_type="monitor",
                object_id=monitor["id"],
                detail={"game_id": game_id, "queue_id": queue_id},
            )
            continue
        result.in_flex += 1
        store.record_monitor_check(monitor_id=monitor["id"], status="in_flex", game_id=game_id, queue_id=queue_id)
        store.add_log(
            level="info",
            category="monitor",
            message=f"{monitor['riot_id']} is in Flex",
            object_type="monitor",
            object_id=monitor["id"],
            detail={"game_id": game_id, "queue_id": queue_id},
        )
        if not webhook_url or not game_id:
            continue
        variables = {
            "riot_id": monitor["riot_id"],
            "game_id": game_id,
            "queue_id": queue_id,
            "started_at": _game_started_at(game),
            "checked_at": checked_at,
            "platform": "jp1",
        }
        payload = render_template(webhook_template, variables)
        inserted = store.insert_notification_once(
            monitor_id=monitor["id"],
            puuid=monitor["puuid"],
            game_id=game_id,
            webhook_url=webhook_url,
            payload=payload,
            response_status=None,
            response_body=None,
        )
        if not inserted:
            store.add_log(
                level="debug",
                category="webhook",
                message="Skipped duplicate Flex notification",
                object_type="monitor",
                object_id=monitor["id"],
                detail={"game_id": game_id},
            )
            continue
        status, body = post_json(webhook_url, payload)
        store.update_notification_response(puuid=monitor["puuid"], game_id=game_id, status=status, body=body)
        store.add_log(
            level="info",
            category="webhook",
            message="Webhook notification sent",
            object_type="monitor",
            object_id=monitor["id"],
            detail={"game_id": game_id, "response_status": status},
        )
        result.notifications += 1
    return result


def monitor_due(last_checked_utc: str | None, interval_minutes: int) -> bool:
    if not last_checked_utc:
        return True
    try:
        last = datetime.fromisoformat(last_checked_utc)
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return datetime.now(UTC) - last >= timedelta(minutes=interval_minutes)
