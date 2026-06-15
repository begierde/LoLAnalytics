from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "players"

    puuid: Mapped[str] = mapped_column(String(128), primary_key=True)
    riot_id: Mapped[str] = mapped_column(String(160), nullable=False)
    game_name: Mapped[str | None] = mapped_column(String(120))
    tag_line: Mapped[str | None] = mapped_column(String(40))
    summoner_id: Mapped[str | None] = mapped_column(String(128))
    league_points: Mapped[int | None] = mapped_column(Integer)
    wins: Mapped[int | None] = mapped_column(Integer)
    losses: Mapped[int | None] = mapped_column(Integer)
    last_seen_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LeagueSnapshot(Base):
    __tablename__ = "league_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fetched_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    queue: Mapped[str] = mapped_column(String(64), nullable=False)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class LeagueSnapshotEntry(Base):
    __tablename__ = "league_snapshot_entries"

    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("league_snapshots.id", ondelete="CASCADE"),
        primary_key=True,
    )
    puuid: Mapped[str] = mapped_column(ForeignKey("players.puuid", ondelete="CASCADE"), primary_key=True)
    summoner_id: Mapped[str] = mapped_column(String(128), nullable=False)
    league_points: Mapped[int | None] = mapped_column(Integer)
    wins: Mapped[int | None] = mapped_column(Integer)
    losses: Mapped[int | None] = mapped_column(Integer)


class Match(Base):
    __tablename__ = "matches"

    match_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    queue_id: Mapped[int | None] = mapped_column(Integer)
    game_start_ms: Mapped[int | None] = mapped_column(BigInteger)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    fetched_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PlayerMatch(Base):
    __tablename__ = "player_matches"

    puuid: Mapped[str] = mapped_column(ForeignKey("players.puuid", ondelete="CASCADE"), primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.match_id", ondelete="CASCADE"), primary_key=True)


class CollectionJob(Base):
    __tablename__ = "collection_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    limit_players: Mapped[int | None] = mapped_column(Integer)
    refresh_league: Mapped[bool] = mapped_column(Boolean, nullable=False)
    server: Mapped[str] = mapped_column(String(16), nullable=False, default="JP")
    rank_scope: Mapped[str] = mapped_column(String(64), nullable=False, default="challenger")
    progress_current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MonitoredPlayer(Base):
    __tablename__ = "monitored_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    puuid: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    riot_id: Mapped[str] = mapped_column(String(160), nullable=False)
    game_name: Mapped[str] = mapped_column(String(120), nullable=False)
    tag_line: Mapped[str] = mapped_column(String(40), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_checked_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(64))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MonitorCheck(Base):
    __tablename__ = "monitor_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    monitored_player_id: Mapped[int] = mapped_column(
        ForeignKey("monitored_players.id", ondelete="CASCADE"),
        nullable=False,
    )
    checked_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    game_id: Mapped[str | None] = mapped_column(String(80))
    queue_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[str | None] = mapped_column(Text)


class MonitorNotification(Base):
    __tablename__ = "monitor_notifications"
    __table_args__ = (UniqueConstraint("puuid", "game_id", name="uq_monitor_notification_puuid_game"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    monitored_player_id: Mapped[int] = mapped_column(
        ForeignKey("monitored_players.id", ondelete="CASCADE"),
        nullable=False,
    )
    puuid: Mapped[str] = mapped_column(String(128), nullable=False)
    game_id: Mapped[str] = mapped_column(String(80), nullable=False)
    sent_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    webhook_url: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[str | None] = mapped_column(Text)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AppLog(Base):
    __tablename__ = "app_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    object_type: Mapped[str | None] = mapped_column(String(64))
    object_id: Mapped[str | None] = mapped_column(String(80))
    detail_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
