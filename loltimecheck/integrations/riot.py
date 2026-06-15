from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class RiotApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class CurrentGameNotFound(RiotApiError):
    pass


@dataclass
class RiotClient:
    api_key: str
    platform_route: str = "jp1"
    regional_route: str = "asia"
    max_retries: int = 4
    timeout: int = 30

    @property
    def platform_host(self) -> str:
        return f"{self.platform_route}.api.riotgames.com"

    @property
    def regional_host(self) -> str:
        return f"{self.regional_route}.api.riotgames.com"

    def _request(self, host: str, path: str, params: dict[str, Any] | None = None) -> Any:
        query = f"?{urlencode(params)}" if params else ""
        url = f"https://{host}{path}{query}"
        request = Request(url, headers={"X-Riot-Token": self.api_key, "User-Agent": "LoLAnalytics/1.0"})
        for attempt in range(self.max_retries + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    body = response.read().decode("utf-8")
                    return json.loads(body) if body else None
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if exc.code == 404 and "active game" in detail.lower():
                    raise CurrentGameNotFound("No active game for summoner") from exc
                if exc.code == 429 and attempt < self.max_retries:
                    retry_after = exc.headers.get("Retry-After")
                    delay = int(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                    time.sleep(max(delay, 1))
                    continue
                if exc.code == 401 and "Unknown apikey" in detail:
                    raise RiotApiError(
                        "Riot API rejected RIOT_API_KEY with 401 Unknown apikey. "
                        "Save a fresh key in Settings. "
                        f"Request URL: {url}",
                        status_code=exc.code,
                    ) from exc
                raise RiotApiError(f"Riot API HTTP {exc.code} for {url}: {detail}", status_code=exc.code) from exc
            except OSError as exc:
                if attempt < self.max_retries:
                    time.sleep(2**attempt)
                    continue
                raise RiotApiError(f"Riot API request failed for {url}: {exc}") from exc
        raise RiotApiError(f"Riot API request failed after retries: {url}")

    def get_challenger_flex(self) -> dict:
        return self.get_flex_league("CHALLENGER")

    def get_flex_league(self, tier: str) -> dict:
        endpoints = {
            "CHALLENGER": "/lol/league/v4/challengerleagues/by-queue/RANKED_FLEX_SR",
            "GRANDMASTER": "/lol/league/v4/grandmasterleagues/by-queue/RANKED_FLEX_SR",
            "MASTER": "/lol/league/v4/masterleagues/by-queue/RANKED_FLEX_SR",
        }
        if tier not in endpoints:
            raise ValueError(f"Unsupported tier: {tier}")
        return self._request(self.platform_host, endpoints[tier])

    def get_summoner_by_id(self, encrypted_summoner_id: str) -> dict:
        return self._request(
            self.platform_host,
            f"/lol/summoner/v4/summoners/{encrypted_summoner_id}",
        )

    def get_summoner_by_puuid(self, puuid: str) -> dict:
        return self._request(self.platform_host, f"/lol/summoner/v4/summoners/by-puuid/{puuid}")

    def get_account_by_puuid(self, puuid: str) -> dict:
        return self._request(self.regional_host, f"/riot/account/v1/accounts/by-puuid/{puuid}")

    def get_account_by_riot_id(self, game_name: str, tag_line: str) -> dict:
        return self._request(
            self.regional_host,
            f"/riot/account/v1/accounts/by-riot-id/{quote(game_name, safe='')}/{quote(tag_line, safe='')}",
        )

    def get_match_ids(
        self,
        puuid: str,
        *,
        start_epoch: int,
        end_epoch: int,
        queue: int = 440,
        count: int = 100,
    ) -> list[str]:
        all_ids: list[str] = []
        start = 0
        while True:
            page = self._request(
                self.regional_host,
                f"/lol/match/v5/matches/by-puuid/{puuid}/ids",
                {
                    "startTime": start_epoch,
                    "endTime": end_epoch,
                    "queue": queue,
                    "start": start,
                    "count": count,
                },
            )
            if not page:
                break
            all_ids.extend(page)
            if len(page) < count:
                break
            start += count
        return all_ids

    def get_match(self, match_id: str) -> dict:
        return self._request(self.regional_host, f"/lol/match/v5/matches/{match_id}")

    def get_current_game_by_puuid(self, puuid: str) -> dict:
        summoner = self.get_summoner_by_puuid(puuid)
        encrypted_summoner_id = summoner.get("id")
        if not encrypted_summoner_id:
            raise RiotApiError(f"Summoner lookup for {puuid[:8]} did not return id")
        return self._request(
            self.platform_host,
            f"/lol/spectator/v5/active-games/by-summoner/{encrypted_summoner_id}",
        )
