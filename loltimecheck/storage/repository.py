from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from loltimecheck.analysis import FLEX_QUEUE_ID
from loltimecheck.core.constants import DEFAULT_LANGUAGE, DEFAULT_RANK_SCOPE, DEFAULT_SERVER
from loltimecheck.integrations.webhook import DEFAULT_TEMPLATE
from loltimecheck.storage.models import (
    AppLog,
    AppSetting,
    Base,
    CollectionJob,
    LeagueSnapshot,
    LeagueSnapshotEntry,
    Match,
    MonitorCheck,
    MonitorNotification,
    MonitoredPlayer,
    Player,
    PlayerMatch,
)
from loltimecheck.storage.session import make_session_factory


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def epoch_ms_days_ago(days: int) -> int:
    return int((utc_now() - timedelta(days=days)).timestamp() * 1000)


def _dt(value: object) -> object:
    return value.isoformat() if isinstance(value, datetime) else value


def _model_dict(obj: object) -> dict:
    data = {column.name: getattr(obj, column.name) for column in obj.__table__.columns}
    return {key: _dt(value) for key, value in data.items()}


def _json_string(value: object) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value or {}, ensure_ascii=False)


class Store:
    def __init__(self, database_url: str | Path):
        raw_url = str(database_url)
        if "://" not in raw_url:
            path = Path(raw_url).resolve().as_posix()
            raw_url = f"sqlite:///{path}"
        self.database_url = raw_url
        self.SessionLocal = make_session_factory(raw_url)
        self.engine = self.SessionLocal.kw["bind"]
        self.session: Session = self.SessionLocal()

    def close(self) -> None:
        self.session.close()
        if self.database_url.startswith("sqlite"):
            self.engine.dispose()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type:
            self.session.rollback()
        self.close()

    def init_schema(self) -> None:
        # Production MySQL schema is managed by Alembic. This keeps local sqlite tests usable.
        if self.database_url.startswith("sqlite"):
            Base.metadata.create_all(self.session.get_bind())
        self.set_setting_default("monitor_interval_minutes", "15")
        self.set_setting_default("webhook_url", "")
        self.set_setting_default("webhook_template", DEFAULT_TEMPLATE)
        self.set_setting_default("ui_language", DEFAULT_LANGUAGE)
        self.set_setting_default("default_server", DEFAULT_SERVER)
        self.set_setting_default("default_rank_scope", DEFAULT_RANK_SCOPE)
        self.set_setting_default("riot_api_key", "")
        self.set_setting_default("last_api_key_check", "")
        self.session.commit()

    def set_setting_default(self, key: str, value: str) -> None:
        if not self.session.get(AppSetting, key):
            self.session.add(AppSetting(key=key, value=value, updated_at_utc=utc_now()))

    def get_settings(self) -> dict[str, str]:
        rows = self.session.scalars(select(AppSetting)).all()
        return {row.key: row.value for row in rows}

    def update_settings(self, settings: dict[str, str]) -> None:
        for key, value in settings.items():
            row = self.session.get(AppSetting, key)
            if row:
                row.value = value
                row.updated_at_utc = utc_now()
            else:
                self.session.add(AppSetting(key=key, value=value, updated_at_utc=utc_now()))
        self.session.commit()

    def purge_older_than(self, retention_days: int) -> None:
        cutoff_ms = epoch_ms_days_ago(retention_days)
        cutoff_dt = utc_now() - timedelta(days=retention_days)
        stale_match_ids = select(Match.match_id).where(Match.game_start_ms < cutoff_ms)
        self.session.execute(delete(PlayerMatch).where(PlayerMatch.match_id.in_(stale_match_ids)))
        self.session.execute(delete(Match).where(Match.game_start_ms < cutoff_ms))
        self.session.execute(delete(LeagueSnapshot).where(LeagueSnapshot.fetched_at_utc < cutoff_dt))
        self.session.execute(delete(CollectionJob).where(CollectionJob.created_at_utc < cutoff_dt))
        self.session.execute(delete(MonitorCheck).where(MonitorCheck.checked_at_utc < cutoff_dt))
        self.session.execute(delete(AppLog).where(AppLog.created_at_utc < cutoff_dt))
        self.session.commit()

    def get_riot_api_key(self) -> str | None:
        key = self.get_settings().get("riot_api_key", "").strip()
        return key or None

    def masked_riot_api_key(self) -> str:
        key = self.get_riot_api_key()
        if not key:
            return ""
        if len(key) <= 12:
            return "*" * len(key)
        return f"{key[:6]}...{key[-4:]}"

    def add_log(
        self,
        *,
        level: str,
        category: str,
        message: str,
        object_type: str | None = None,
        object_id: str | int | None = None,
        detail: dict | None = None,
    ) -> None:
        self.session.add(
            AppLog(
                created_at_utc=utc_now(),
                level=level,
                category=category,
                message=message,
                object_type=object_type,
                object_id=str(object_id) if object_id is not None else None,
                detail_json=detail or {},
            )
        )
        self.session.commit()

    def count_logs(self, *, level: str | None = None, category: str | None = None) -> int:
        stmt = select(func.count()).select_from(AppLog)
        if level:
            stmt = stmt.where(AppLog.level == level)
        if category:
            stmt = stmt.where(AppLog.category == category)
        return int(self.session.scalar(stmt) or 0)

    def list_logs(
        self,
        *,
        level: str | None = None,
        category: str | None = None,
        limit: int = 100,
        offset: int = 0,
        cursor: int | None = None,
    ) -> list[dict]:
        stmt = select(AppLog)
        if level:
            stmt = stmt.where(AppLog.level == level)
        if category:
            stmt = stmt.where(AppLog.category == category)
        if cursor:
            stmt = stmt.where(AppLog.id < cursor)
        stmt = stmt.order_by(AppLog.id.desc()).limit(max(1, min(limit, 500))).offset(max(0, offset))
        return [_model_dict(row) for row in self.session.scalars(stmt).all()]

    def clear_logs(self) -> None:
        self.session.execute(delete(AppLog))
        self.session.commit()

    def upsert_player(
        self,
        *,
        puuid: str,
        riot_id: str,
        game_name: str | None,
        tag_line: str | None,
        summoner_id: str | None,
        league_points: int | None,
        wins: int | None,
        losses: int | None,
    ) -> None:
        player = self.session.get(Player, puuid)
        if not player:
            player = Player(puuid=puuid, riot_id=riot_id, last_seen_utc=utc_now())
            self.session.add(player)
        player.riot_id = riot_id
        player.game_name = game_name
        player.tag_line = tag_line
        player.summoner_id = summoner_id
        player.league_points = league_points
        player.wins = wins
        player.losses = losses
        player.last_seen_utc = utc_now()
        self.session.commit()

    def insert_league_snapshot(self, league: dict) -> int:
        row = LeagueSnapshot(
            fetched_at_utc=utc_now(),
            queue=league.get("queue") or "RANKED_FLEX_SR",
            tier=league.get("tier") or "CHALLENGER",
            raw_json=league,
        )
        self.session.add(row)
        self.session.commit()
        return int(row.id)

    def insert_snapshot_entry(self, snapshot_id: int, puuid: str, entry: dict) -> None:
        row = self.session.get(LeagueSnapshotEntry, (snapshot_id, puuid))
        if not row:
            row = LeagueSnapshotEntry(snapshot_id=snapshot_id, puuid=puuid, summoner_id="")
            self.session.add(row)
        row.summoner_id = entry.get("summonerId") or entry.get("summonerName") or puuid
        row.league_points = entry.get("leaguePoints")
        row.wins = entry.get("wins")
        row.losses = entry.get("losses")
        self.session.commit()

    def list_players(self, limit: int | None = None) -> list[dict]:
        stmt = select(Player).order_by(Player.league_points.desc(), Player.riot_id.asc())
        if limit is not None:
            stmt = stmt.limit(limit)
        return [_model_dict(row) for row in self.session.scalars(stmt).all()]

    def has_players(self) -> bool:
        return self.session.scalar(select(Player.puuid).limit(1)) is not None

    def upsert_match(self, match_id: str, match: dict) -> bool:
        info = match.get("info") or {}
        row = self.session.get(Match, match_id)
        if row:
            return False
        self.session.add(
            Match(
                match_id=match_id,
                queue_id=info.get("queueId"),
                game_start_ms=info.get("gameStartTimestamp"),
                raw_json=match,
                fetched_at_utc=utc_now(),
            )
        )
        self.session.commit()
        return True

    def has_match(self, match_id: str) -> bool:
        return self.session.get(Match, match_id) is not None

    def get_match(self, match_id: str) -> dict | None:
        row = self.session.get(Match, match_id)
        return row.raw_json if row else None

    def link_player_match(self, puuid: str, match_id: str) -> None:
        if not self.session.get(PlayerMatch, (puuid, match_id)):
            self.session.add(PlayerMatch(puuid=puuid, match_id=match_id))
            self.session.commit()

    def iter_events(self, start_ms: int, end_ms: int) -> Iterable[dict]:
        stmt = (
            select(PlayerMatch.puuid, Player.riot_id, Player.league_points, Match.match_id, Match.game_start_ms, Match.raw_json)
            .join(Player, Player.puuid == PlayerMatch.puuid)
            .join(Match, Match.match_id == PlayerMatch.match_id)
            .where(and_(Match.queue_id == FLEX_QUEUE_ID, Match.game_start_ms >= start_ms, Match.game_start_ms <= end_ms))
            .order_by(Match.game_start_ms.asc())
        )
        return [dict(row) for row in self.session.execute(stmt).mappings().all()]

    def create_job(
        self,
        *,
        days: int,
        timezone: str,
        limit_players: int | None,
        refresh_league: bool,
        server: str = DEFAULT_SERVER,
        rank_scope: str = DEFAULT_RANK_SCOPE,
    ) -> int:
        row = CollectionJob(
            status="pending",
            days=days,
            timezone=timezone,
            limit_players=limit_players,
            refresh_league=refresh_league,
            server=server,
            rank_scope=rank_scope,
            progress_current=0,
            progress_total=0,
            message="Queued",
            created_at_utc=utc_now(),
        )
        self.session.add(row)
        self.session.commit()
        return int(row.id)

    def update_job(self, job_id: int, **fields: object) -> None:
        if not fields:
            return
        normalized = {key: (datetime.fromisoformat(value) if key.endswith("_utc") and isinstance(value, str) else value) for key, value in fields.items()}
        self.session.execute(update(CollectionJob).where(CollectionJob.id == job_id).values(**normalized))
        self.session.commit()

    def claim_next_pending_job(self) -> dict | None:
        stmt = (
            select(CollectionJob)
            .where(CollectionJob.status == "pending")
            .order_by(CollectionJob.id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        with self.session.begin():
            row = self.session.scalars(stmt).first()
            if not row:
                return None
            row.status = "running"
            row.started_at_utc = utc_now()
            row.message = "Collecting data"
            self.session.flush()
            return _model_dict(row)

    def get_job(self, job_id: int) -> dict | None:
        row = self.session.get(CollectionJob, job_id)
        return _model_dict(row) if row else None

    def count_jobs(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(CollectionJob)) or 0)

    def list_jobs(self, limit: int = 20, offset: int = 0) -> list[dict]:
        stmt = (
            select(CollectionJob)
            .order_by(CollectionJob.id.desc())
            .limit(max(1, min(limit, 500)))
            .offset(max(0, offset))
        )
        return [_model_dict(row) for row in self.session.scalars(stmt).all()]

    def upsert_monitor(self, *, puuid: str, riot_id: str, game_name: str, tag_line: str) -> int:
        row = self.session.scalar(select(MonitoredPlayer).where(MonitoredPlayer.puuid == puuid))
        if not row:
            row = MonitoredPlayer(puuid=puuid, riot_id=riot_id, game_name=game_name, tag_line=tag_line, created_at_utc=utc_now())
            self.session.add(row)
        row.riot_id = riot_id
        row.game_name = game_name
        row.tag_line = tag_line
        row.enabled = True
        self.session.commit()
        return int(row.id)

    def list_monitors(self, enabled_only: bool = False) -> list[dict]:
        stmt = select(MonitoredPlayer)
        if enabled_only:
            stmt = stmt.where(MonitoredPlayer.enabled.is_(True))
        stmt = stmt.order_by(MonitoredPlayer.riot_id.asc())
        return [_model_dict(row) for row in self.session.scalars(stmt).all()]

    def set_monitor_enabled(self, monitor_id: int, enabled: bool) -> None:
        self.session.execute(update(MonitoredPlayer).where(MonitoredPlayer.id == monitor_id).values(enabled=enabled))
        self.session.commit()

    def delete_monitor(self, monitor_id: int) -> None:
        self.session.execute(delete(MonitoredPlayer).where(MonitoredPlayer.id == monitor_id))
        self.session.commit()

    def record_monitor_check(
        self,
        *,
        monitor_id: int,
        status: str,
        game_id: str | None = None,
        queue_id: int | None = None,
        detail: str | None = None,
    ) -> None:
        checked_at = utc_now()
        self.session.add(
            MonitorCheck(
                monitored_player_id=monitor_id,
                checked_at_utc=checked_at,
                status=status,
                game_id=game_id,
                queue_id=queue_id,
                detail=detail,
            )
        )
        self.session.execute(
            update(MonitoredPlayer)
            .where(MonitoredPlayer.id == monitor_id)
            .values(last_checked_utc=checked_at, last_status=status)
        )
        self.session.commit()

    def insert_notification_once(
        self,
        *,
        monitor_id: int,
        puuid: str,
        game_id: str,
        webhook_url: str,
        payload: dict,
        response_status: int | None,
        response_body: str | None,
    ) -> bool:
        self.session.add(
            MonitorNotification(
                monitored_player_id=monitor_id,
                puuid=puuid,
                game_id=game_id,
                sent_at_utc=utc_now(),
                webhook_url=webhook_url,
                payload_json=payload,
                response_status=response_status,
                response_body=response_body,
            )
        )
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            return False
        return True

    def update_notification_response(self, *, puuid: str, game_id: str, status: int, body: str) -> None:
        self.session.execute(
            update(MonitorNotification)
            .where(and_(MonitorNotification.puuid == puuid, MonitorNotification.game_id == game_id))
            .values(response_status=status, response_body=body[:1000])
        )
        self.session.commit()
