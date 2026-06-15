from __future__ import annotations

import hmac
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

from loltimecheck.core.config import AppConfig
from loltimecheck.core.constants import DEFAULT_SERVER, DEFAULT_TIMEZONE, rank_scope_tiers, server_routes
from loltimecheck.integrations.riot import RiotClient
from loltimecheck.integrations.webhook import render_template
from loltimecheck.services.jobs import JobService
from loltimecheck.services.monitoring import add_monitor, check_monitors
from loltimecheck.services.settings import check_riot_api_key, settings_payload
from loltimecheck.services.stats import stats_payload
from loltimecheck.storage.repository import Store
from loltimecheck.web.auth import auth_dependency, clear_session_cookie, create_token, require_configured_auth, set_session_cookie
from loltimecheck.web.schemas import ApiKeyCheckRequest, CollectRequest, LoginRequest, MonitorCreate, MonitorUpdate, SettingsUpdate


def create_app(config: AppConfig | None = None) -> FastAPI:
    config = config or AppConfig.from_env()
    job_service = JobService(config)
    require_auth = auth_dependency(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        with Store(config.database_url) as store:
            store.init_schema()
            store.purge_older_than(config.retention_days)
        yield

    app = FastAPI(title="LoLAnalytics API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/v1/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/api/v1/auth/login")
    def login(payload: LoginRequest, response: Response) -> dict:
        require_configured_auth(config)
        if not hmac.compare_digest(payload.password, config.admin_password):
            raise HTTPException(status_code=401, detail="Invalid password")
        token = create_token(config)
        set_session_cookie(response, config, token)
        return {"authenticated": True, "accessToken": token, "tokenType": "bearer"}

    @app.post("/api/v1/auth/token")
    def token(response: Response, form: OAuth2PasswordRequestForm = Depends()) -> dict:
        require_configured_auth(config)
        if not hmac.compare_digest(form.password, config.admin_password):
            raise HTTPException(status_code=401, detail="Invalid password")
        access_token = create_token(config, subject=form.username or "admin")
        set_session_cookie(response, config, access_token)
        return {"access_token": access_token, "token_type": "bearer"}

    @app.post("/api/v1/auth/logout")
    def logout(response: Response) -> dict:
        clear_session_cookie(response, config)
        return {"authenticated": False}

    @app.get("/api/v1/auth/session")
    def session(_: dict = Depends(require_auth)) -> dict:
        return {"authenticated": True}

    @app.post("/api/v1/collection-jobs")
    def create_collection_job(payload: CollectRequest, _: dict = Depends(require_auth)) -> dict:
        try:
            server_routes(payload.server)
            rank_scope_tiers(payload.rankScope)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        job_id = job_service.create_collection_job(
            days=payload.days,
            timezone=payload.timezone,
            limit_players=payload.limitPlayers,
            refresh_league=payload.refreshLeague,
            server=payload.server,
            rank_scope=payload.rankScope,
        )
        return {"jobId": job_id}

    @app.get("/api/v1/collection-jobs/{job_id}")
    def get_collection_job(job_id: int, _: dict = Depends(require_auth)) -> dict:
        with Store(config.database_url) as store:
            store.init_schema()
            row = store.get_job(job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return row

    @app.get("/api/v1/collection-jobs")
    def list_collection_jobs(page: int = 1, pageSize: int = 10, _: dict = Depends(require_auth)) -> dict:
        page = max(1, page)
        page_size = max(1, min(pageSize, 100))
        offset = (page - 1) * page_size
        with Store(config.database_url) as store:
            store.init_schema()
            total = store.count_jobs()
            jobs = store.list_jobs(limit=page_size, offset=offset)
        return {
            "jobs": jobs,
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": total,
                "totalPages": (total + page_size - 1) // page_size if total else 0,
            },
        }

    @app.get("/api/v1/stats")
    def stats(
        days: int = 30,
        timezone: str = DEFAULT_TIMEZONE,
        playerPage: int = 1,
        playerPageSize: int = 10,
        _: dict = Depends(require_auth),
    ) -> dict:
        if days < 1 or days > 365:
            raise HTTPException(status_code=400, detail="days must be between 1 and 365")
        with Store(config.database_url) as store:
            store.init_schema()
            try:
                return stats_payload(
                    store,
                    days=days,
                    timezone=timezone,
                    player_page=playerPage,
                    player_page_size=playerPageSize,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/monitors")
    def list_monitors(_: dict = Depends(require_auth)) -> dict:
        with Store(config.database_url) as store:
            store.init_schema()
            monitors = store.list_monitors()
        return {"monitors": monitors}

    @app.post("/api/v1/monitors")
    def create_monitor(payload: MonitorCreate, _: dict = Depends(require_auth)) -> dict:
        with Store(config.database_url) as store:
            store.init_schema()
            api_key = store.get_riot_api_key()
            if not api_key:
                store.add_log(level="error", category="monitor", message="Riot API key is not configured")
                raise HTTPException(status_code=400, detail="Riot API key is not configured. Save it in Settings first.")
            routes = server_routes(store.get_settings().get("default_server", DEFAULT_SERVER))
            client = RiotClient(api_key, platform_route=routes["platform"], regional_route=routes["regional"])
            try:
                monitor_id = add_monitor(store, client, payload.riotId)
            except ValueError as exc:
                store.add_log(level="error", category="monitor", message=str(exc), detail={"riot_id": payload.riotId})
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            row = next((row for row in store.list_monitors() if row["id"] == monitor_id), None)
            store.add_log(
                level="info",
                category="monitor",
                message="Monitor saved",
                object_type="monitor",
                object_id=monitor_id,
                detail={"riot_id": payload.riotId},
            )
        return row or {}

    @app.patch("/api/v1/monitors/{monitor_id}")
    def update_monitor(monitor_id: int, payload: MonitorUpdate, _: dict = Depends(require_auth)) -> dict:
        with Store(config.database_url) as store:
            store.init_schema()
            store.set_monitor_enabled(monitor_id, payload.enabled)
        return {"updated": True}

    @app.delete("/api/v1/monitors/{monitor_id}")
    def delete_monitor(monitor_id: int, _: dict = Depends(require_auth)) -> dict:
        with Store(config.database_url) as store:
            store.init_schema()
            store.delete_monitor(monitor_id)
        return {"deleted": True}

    @app.post("/api/v1/monitor-checks")
    def create_monitor_check(_: dict = Depends(require_auth)) -> dict:
        with Store(config.database_url) as store:
            store.init_schema()
            api_key = store.get_riot_api_key()
            if not api_key:
                store.add_log(level="error", category="monitor", message="Riot API key is not configured")
                raise HTTPException(status_code=400, detail="Riot API key is not configured. Save it in Settings first.")
            routes = server_routes(store.get_settings().get("default_server", DEFAULT_SERVER))
            client = RiotClient(api_key, platform_route=routes["platform"], regional_route=routes["regional"])
            result = check_monitors(store, client)
        return result.__dict__

    @app.get("/api/v1/settings")
    def get_settings(_: dict = Depends(require_auth)) -> dict:
        with Store(config.database_url) as store:
            store.init_schema()
            return settings_payload(store)

    @app.put("/api/v1/settings")
    def update_settings(payload: SettingsUpdate, _: dict = Depends(require_auth)) -> dict:
        try:
            server_routes(payload.defaultServer)
            rank_scope_tiers(payload.defaultRankScope)
            render_template(
                payload.webhookTemplate,
                {
                    "riot_id": "Example#JP1",
                    "game_id": "123",
                    "queue_id": 440,
                    "started_at": "2026-06-13T00:00:00+00:00",
                    "checked_at": "2026-06-13T00:15:00+00:00",
                    "platform": config.platform_route,
                },
            )
        except ValueError as exc:
            with Store(config.database_url) as store:
                store.init_schema()
                store.add_log(level="error", category="settings", message=str(exc))
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        with Store(config.database_url) as store:
            store.init_schema()
            updates = {
                "monitor_interval_minutes": str(payload.monitorIntervalMinutes),
                "webhook_url": payload.webhookUrl,
                "webhook_template": payload.webhookTemplate,
                "ui_language": payload.language,
                "default_server": payload.defaultServer,
                "default_rank_scope": payload.defaultRankScope,
            }
            if payload.riotApiKey is not None and payload.riotApiKey.strip():
                updates["riot_api_key"] = payload.riotApiKey.strip()
            store.update_settings(updates)
            store.add_log(
                level="info",
                category="settings",
                message="Settings saved",
                detail={
                    "language": payload.language,
                    "default_server": payload.defaultServer,
                    "default_rank_scope": payload.defaultRankScope,
                    "api_key_updated": "riot_api_key" in updates,
                },
            )
        return {"updated": True}

    @app.post("/api/v1/settings/riot-api-key-checks")
    def check_api_key(payload: ApiKeyCheckRequest | None = None, _: dict = Depends(require_auth)) -> dict:
        with Store(config.database_url) as store:
            store.init_schema()
            try:
                return check_riot_api_key(store, server=payload.server if payload else None)
            except ValueError as exc:
                store.add_log(level="error", category="api_key", message=str(exc))
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/v1/logs")
    def list_logs(
        level: str | None = None,
        category: str | None = None,
        limit: int = 100,
        cursor: int | None = None,
        page: int = 1,
        pageSize: int | None = None,
        _: dict = Depends(require_auth),
    ) -> dict:
        effective_page_size = pageSize if pageSize is not None else limit
        page = max(1, page)
        page_size = max(1, min(effective_page_size, 500))
        offset = (page - 1) * page_size
        with Store(config.database_url) as store:
            store.init_schema()
            total = store.count_logs(level=level, category=category)
            rows = store.list_logs(level=level, category=category, limit=page_size, offset=offset, cursor=cursor)
        for row in rows:
            row["detail"] = row.get("detail_json") or {}
            row.pop("detail_json", None)
        next_cursor = rows[-1]["id"] if rows else None
        return {
            "logs": rows,
            "nextCursor": next_cursor,
            "pagination": {
                "page": page,
                "pageSize": page_size,
                "total": total,
                "totalPages": (total + page_size - 1) // page_size if total else 0,
            },
        }

    @app.delete("/api/v1/logs")
    def clear_logs(_: dict = Depends(require_auth)) -> dict:
        with Store(config.database_url) as store:
            store.init_schema()
            store.clear_logs()
            store.add_log(level="info", category="logs", message="Logs cleared")
        return {"cleared": True}

    return app


app = create_app()
