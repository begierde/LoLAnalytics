from __future__ import annotations

import os
import time

from loltimecheck.core.config import AppConfig
from loltimecheck.core.constants import DEFAULT_SERVER, server_routes
from loltimecheck.integrations.riot import RiotClient
from loltimecheck.services.jobs import CollectionWorker
from loltimecheck.services.monitoring import check_monitors
from loltimecheck.storage.repository import Store


class Worker:
    def __init__(self, config: AppConfig):
        self.config = config
        self.collection_worker = CollectionWorker(config)
        self.last_monitor_check = 0.0

    def tick(self) -> None:
        claimed = self.collection_worker.run_once()
        if not claimed:
            self.run_monitor_if_due()

    def run_monitor_if_due(self) -> None:
        now = time.monotonic()
        with Store(self.config.database_url) as store:
            store.init_schema()
            settings = store.get_settings()
            interval_minutes = int(settings.get("monitor_interval_minutes", str(self.config.default_monitor_interval_minutes)))
            due_seconds = max(interval_minutes * 60, 60)
            if now - self.last_monitor_check < due_seconds:
                return
            self.last_monitor_check = now
            api_key = store.get_riot_api_key()
            monitors = store.list_monitors(enabled_only=True)
            if not api_key or not monitors:
                return
            routes = server_routes(settings.get("default_server", DEFAULT_SERVER))
            client = RiotClient(api_key, platform_route=routes["platform"], regional_route=routes["regional"])
            check_monitors(store, client)

    def run_forever(self) -> None:
        interval = float(os.environ.get("WORKER_POLL_SECONDS", "5"))
        while True:
            self.tick()
            time.sleep(max(interval, 1.0))


def main() -> None:
    Worker(AppConfig.from_env()).run_forever()


if __name__ == "__main__":
    main()
