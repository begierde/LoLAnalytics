from __future__ import annotations

from pydantic import BaseModel, Field

from loltimecheck.core.constants import DEFAULT_RANK_SCOPE, DEFAULT_SERVER
from loltimecheck.core.constants import DEFAULT_TIMEZONE


class CollectRequest(BaseModel):
    days: int = Field(default=30, ge=1, le=365)
    timezone: str = DEFAULT_TIMEZONE
    limitPlayers: int | None = Field(default=20, ge=1, le=300)
    refreshLeague: bool = True
    server: str = DEFAULT_SERVER
    rankScope: str = DEFAULT_RANK_SCOPE


class MonitorCreate(BaseModel):
    riotId: str = Field(min_length=3, max_length=120)


class MonitorUpdate(BaseModel):
    enabled: bool


class SettingsUpdate(BaseModel):
    monitorIntervalMinutes: int = Field(default=15, ge=1, le=1440)
    webhookUrl: str = ""
    webhookTemplate: str
    language: str = "zh"
    defaultServer: str = DEFAULT_SERVER
    defaultRankScope: str = DEFAULT_RANK_SCOPE
    riotApiKey: str | None = None


class ApiKeyCheckRequest(BaseModel):
    server: str | None = None


class LoginRequest(BaseModel):
    password: str = Field(min_length=1)
