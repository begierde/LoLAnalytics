from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .constants import (
    DEFAULT_MONITOR_INTERVAL_MINUTES,
    DEFAULT_PLATFORM_ROUTE,
    DEFAULT_REGIONAL_ROUTE,
    DEFAULT_RETENTION_DAYS,
)


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.lstrip("\ufeff").strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class AppConfig:
    database_url: str
    platform_route: str
    regional_route: str
    retention_days: int
    default_monitor_interval_minutes: int
    app_host: str
    app_port: int
    cors_origins: tuple[str, ...]
    admin_password: str
    jwt_secret: str
    session_cookie_name: str = "lolanalytics_session"

    @classmethod
    def for_sqlite(
        cls,
        database_path: str,
        *,
        platform_route: str = DEFAULT_PLATFORM_ROUTE,
        regional_route: str = DEFAULT_REGIONAL_ROUTE,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        default_monitor_interval_minutes: int = DEFAULT_MONITOR_INTERVAL_MINUTES,
        app_host: str = "127.0.0.1",
        app_port: int = 8000,
        admin_password: str = "admin",
        jwt_secret: str = "test-secret",
    ) -> "AppConfig":
        path = Path(database_path).resolve().as_posix()
        return cls(
            database_url=f"sqlite:///{path}",
            platform_route=platform_route,
            regional_route=regional_route,
            retention_days=retention_days,
            default_monitor_interval_minutes=default_monitor_interval_minutes,
            app_host=app_host,
            app_port=app_port,
            cors_origins=("http://localhost:5173", "http://127.0.0.1:5173"),
            admin_password=admin_password,
            jwt_secret=jwt_secret,
        )

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_dotenv()
        origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        return cls(
            database_url=os.environ.get(
                "DATABASE_URL",
                "mysql+pymysql://lolanalytics:lolanalytics@mysql:3306/lolanalytics",
            ),
            platform_route=os.environ.get("PLATFORM_ROUTE", DEFAULT_PLATFORM_ROUTE),
            regional_route=os.environ.get("REGIONAL_ROUTE", DEFAULT_REGIONAL_ROUTE),
            retention_days=int(os.environ.get("RETENTION_DAYS", DEFAULT_RETENTION_DAYS)),
            default_monitor_interval_minutes=int(
                os.environ.get("MONITOR_INTERVAL_MINUTES", DEFAULT_MONITOR_INTERVAL_MINUTES)
            ),
            app_host=os.environ.get("APP_HOST", "0.0.0.0"),
            app_port=int(os.environ.get("APP_PORT", "8000")),
            cors_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip()),
            admin_password=os.environ.get("ADMIN_PASSWORD", ""),
            jwt_secret=os.environ.get("JWT_SECRET", ""),
        )
