from __future__ import annotations

from datetime import UTC, datetime

from loltimecheck.core.config import AppConfig
from loltimecheck.core.constants import DEFAULT_RANK_SCOPE, DEFAULT_SERVER, server_routes
from loltimecheck.integrations.riot import RiotClient
from loltimecheck.services.collection import run_collection
from loltimecheck.storage.repository import Store


class JobService:
    def __init__(self, config: AppConfig):
        self.config = config

    def create_collection_job(
        self,
        *,
        days: int,
        timezone: str,
        limit_players: int | None,
        refresh_league: bool,
        server: str = DEFAULT_SERVER,
        rank_scope: str = DEFAULT_RANK_SCOPE,
    ) -> int:
        with Store(self.config.database_url) as store:
            store.init_schema()
            job_id = store.create_job(
                days=days,
                timezone=timezone,
                limit_players=limit_players,
                refresh_league=refresh_league,
                server=server,
                rank_scope=rank_scope,
            )
            store.add_log(
                level="info",
                category="collection",
                message="Collection job queued",
                object_type="collection_job",
                object_id=job_id,
                detail={"days": days, "server": server, "rank_scope": rank_scope},
            )
            return job_id


class CollectionWorker:
    def __init__(self, config: AppConfig):
        self.config = config

    def run_once(self) -> bool:
        with Store(self.config.database_url) as store:
            store.init_schema()
            job = store.claim_next_pending_job()
            if not job:
                return False
            self._run_claimed_job(store, job)
            return True

    def _run_claimed_job(self, store: Store, job: dict) -> None:
        job_id = int(job["id"])
        server = job.get("server") or DEFAULT_SERVER
        rank_scope = job.get("rank_scope") or DEFAULT_RANK_SCOPE
        try:
            api_key = store.get_riot_api_key()
            if not api_key:
                raise ValueError("Riot API key is not configured. Save it in Settings first.")
            routes = server_routes(server)
            client = RiotClient(api_key, platform_route=routes["platform"], regional_route=routes["regional"])
            store.add_log(
                level="info",
                category="collection",
                message="Collection job started",
                object_type="collection_job",
                object_id=job_id,
                detail={"server": server, "rank_scope": rank_scope},
            )

            def progress(current: int, total: int, message: str) -> None:
                store.update_job(job_id, progress_current=current, progress_total=total, message=message)

            result = run_collection(
                store,
                client,
                days=int(job["days"]),
                limit_players=job.get("limit_players"),
                refresh_league=bool(job["refresh_league"]),
                rank_scope=rank_scope,
                progress=progress,
                retention_days=self.config.retention_days,
            )
            store.update_job(
                job_id,
                status="completed",
                finished_at_utc=datetime.now(UTC).isoformat(),
                message=(
                    f"Completed: {result.players} players, "
                    f"{result.match_ids} match ids, {result.new_matches} new matches"
                ),
            )
            store.add_log(
                level="info",
                category="collection",
                message="Collection job completed",
                object_type="collection_job",
                object_id=job_id,
                detail=result.__dict__,
            )
        except Exception as exc:
            store.update_job(
                job_id,
                status="failed",
                error=str(exc),
                finished_at_utc=datetime.now(UTC).isoformat(),
                message="Failed",
            )
            store.add_log(
                level="error",
                category="collection",
                message=str(exc),
                object_type="collection_job",
                object_id=job_id,
                detail={"server": server, "rank_scope": rank_scope},
            )
