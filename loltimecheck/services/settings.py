from __future__ import annotations

from datetime import UTC, datetime

from loltimecheck.core.constants import (
    DEFAULT_LANGUAGE,
    DEFAULT_RANK_SCOPE,
    DEFAULT_SERVER,
    RANK_SCOPES,
    SERVERS,
    TIMEZONES,
    server_routes,
)
from loltimecheck.integrations.riot import RiotApiError, RiotClient
from loltimecheck.storage.repository import Store


def settings_payload(store: Store) -> dict:
    settings = store.get_settings()
    return {
        "monitorIntervalMinutes": int(settings.get("monitor_interval_minutes", "15")),
        "webhookUrl": settings.get("webhook_url", ""),
        "webhookTemplate": settings.get("webhook_template", "{}"),
        "language": settings.get("ui_language", DEFAULT_LANGUAGE),
        "defaultServer": settings.get("default_server", DEFAULT_SERVER),
        "defaultRankScope": settings.get("default_rank_scope", DEFAULT_RANK_SCOPE),
        "riotApiKeyMasked": store.masked_riot_api_key(),
        "hasRiotApiKey": bool(store.get_riot_api_key()),
        "lastApiKeyCheck": settings.get("last_api_key_check", ""),
        "servers": [
            {"code": code, "label": data["label"], "platform": data["platform"], "regional": data["regional"]}
            for code, data in SERVERS.items()
        ],
        "rankScopes": list(RANK_SCOPES.keys()),
        "timezones": TIMEZONES,
    }


def check_riot_api_key(store: Store, *, server: str | None = None) -> dict:
    api_key = store.get_riot_api_key()
    checked_at = datetime.now(UTC).isoformat()
    if not api_key:
        result = {
            "valid": False,
            "statusCode": None,
            "checkedAt": checked_at,
            "message": "Riot API key is not configured.",
        }
        store.update_settings({"last_api_key_check": result["message"]})
        store.add_log(level="error", category="api_key", message=result["message"], detail=result)
        return result

    selected_server = server or store.get_settings().get("default_server", DEFAULT_SERVER)
    routes = server_routes(selected_server)
    client = RiotClient(api_key, platform_route=routes["platform"], regional_route=routes["regional"])
    try:
        client.get_challenger_flex()
    except RiotApiError as exc:
        result = {
            "valid": False,
            "statusCode": exc.status_code,
            "checkedAt": checked_at,
            "message": str(exc),
        }
        store.update_settings({"last_api_key_check": f"invalid at {checked_at}"})
        store.add_log(level="error", category="api_key", message="Riot API key check failed", detail=result)
        return result

    result = {
        "valid": True,
        "statusCode": 200,
        "checkedAt": checked_at,
        "message": "Riot API key is valid.",
    }
    store.update_settings({"last_api_key_check": f"valid at {checked_at}"})
    store.add_log(level="info", category="api_key", message="Riot API key check passed", detail=result)
    return result
