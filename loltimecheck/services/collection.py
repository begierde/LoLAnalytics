from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from loltimecheck.analysis import FLEX_QUEUE_ID, compute_window, normalize_riot_id
from loltimecheck.core.constants import DEFAULT_RANK_SCOPE, RANK_SCOPES, TIER_PRIORITY, rank_scope_tiers
from loltimecheck.integrations.riot import RiotClient
from loltimecheck.storage.repository import Store


ProgressCallback = Callable[[int, int, str], None]


@dataclass
class CollectionResult:
    players: int
    match_ids: int
    new_matches: int


def collect_league(
    store: Store,
    client: RiotClient,
    limit_players: int | None,
    rank_scope: str = DEFAULT_RANK_SCOPE,
) -> list[dict]:
    merged_entries: list[tuple[str, dict, int]] = []
    snapshot_ids: dict[str, int] = {}
    for tier in rank_scope_tiers(rank_scope):
        league = client.get_flex_league(tier)
        snapshot_ids[tier] = store.insert_league_snapshot(league)
        for entry in league.get("entries") or []:
            merged_entries.append((tier, entry, snapshot_ids[tier]))

    merged_entries.sort(
        key=lambda item: (
            TIER_PRIORITY.get(item[0], 99),
            -(item[1].get("leaguePoints") or 0),
        )
    )
    if limit_players is not None:
        merged_entries = merged_entries[:limit_players]

    players: list[dict] = []
    seen_puuids: set[str] = set()
    for tier, entry, snapshot_id in merged_entries:
        summoner_id = entry.get("summonerId")
        puuid = entry.get("puuid")
        if not puuid and summoner_id:
            puuid = client.get_summoner_by_id(summoner_id).get("puuid")
        if not puuid or puuid in seen_puuids:
            continue
        seen_puuids.add(puuid)
        account = client.get_account_by_puuid(puuid)
        game_name = account.get("gameName")
        tag_line = account.get("tagLine")
        riot_id = normalize_riot_id(game_name, tag_line, puuid)
        store.upsert_player(
            puuid=puuid,
            riot_id=riot_id,
            game_name=game_name,
            tag_line=tag_line,
            summoner_id=summoner_id,
            league_points=entry.get("leaguePoints"),
            wins=entry.get("wins"),
            losses=entry.get("losses"),
        )
        store.insert_snapshot_entry(snapshot_id, puuid, entry)
        players.append({"puuid": puuid, "riot_id": riot_id, "tier": tier})
    return players


def collect_matches(
    store: Store,
    client: RiotClient,
    players: list[dict],
    *,
    days: int,
    progress: ProgressCallback | None = None,
) -> CollectionResult:
    window = compute_window(days)
    total_ids = 0
    new_matches = 0
    for index, player in enumerate(players, start=1):
        puuid = player["puuid"]
        riot_id = player.get("riot_id") or puuid[:8]
        match_ids = client.get_match_ids(
            puuid,
            start_epoch=window.start_epoch,
            end_epoch=window.end_epoch,
            queue=FLEX_QUEUE_ID,
        )
        total_ids += len(match_ids)
        if progress:
            progress(index, len(players), f"{riot_id}: {len(match_ids)} match ids")
        for match_id in match_ids:
            match = store.get_match(match_id)
            if match is None:
                match = client.get_match(match_id)
                if store.upsert_match(match_id, match):
                    new_matches += 1
            info = match.get("info") or {}
            if info.get("queueId") == FLEX_QUEUE_ID:
                store.link_player_match(puuid, match_id)
    return CollectionResult(players=len(players), match_ids=total_ids, new_matches=new_matches)


def run_collection(
    store: Store,
    client: RiotClient,
    *,
    days: int,
    limit_players: int | None,
    refresh_league: bool,
    rank_scope: str = DEFAULT_RANK_SCOPE,
    progress: ProgressCallback | None = None,
    retention_days: int = 365,
) -> CollectionResult:
    if refresh_league or not store.has_players():
        players = collect_league(store, client, limit_players, rank_scope=rank_scope)
    else:
        players = [
            {"puuid": row["puuid"], "riot_id": row["riot_id"]}
            for row in store.list_players(limit_players)
        ]
    result = collect_matches(store, client, players, days=days, progress=progress)
    store.purge_older_than(retention_days)
    return result
