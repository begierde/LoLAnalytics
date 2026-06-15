from __future__ import annotations

import json
from string import Template
from urllib.request import Request, urlopen


DEFAULT_TEMPLATE = json.dumps(
    {
        "text": "$riot_id is in Flex queue.",
        "riot_id": "$riot_id",
        "game_id": "$game_id",
        "queue_id": "$queue_id",
        "started_at": "$started_at",
        "checked_at": "$checked_at",
        "platform": "$platform",
    },
    ensure_ascii=False,
)


def render_template(template: str, variables: dict[str, object]) -> dict:
    rendered = Template(template).safe_substitute({k: str(v) for k, v in variables.items()})
    try:
        payload = json.loads(rendered)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Webhook template must render to JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Webhook template must render to a JSON object")
    return payload


def post_json(url: str, payload: dict, timeout: int = 15) -> tuple[int, str]:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "LoLAnalytics/1.0"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8", errors="replace")
