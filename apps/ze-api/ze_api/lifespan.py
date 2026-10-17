from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from ze_api.cli import migrate as ze_migrate
from ze_api.settings import get_settings
from ze_api.wiring.container import build_container
from ze_api.wiring.plugin_routes import mount_plugin_routers
from ze_logging import configure_logging, get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(
        settings.log_level,
        dev=settings.log_dev,
        log_file=settings.log_file,
    )

    if settings.auto_migrate:
        log.info("ze_auto_migrate_start")
        ze_migrate.upgrade(settings.database_url_sync)
        log.info("ze_auto_migrate_done")

    ze_migrate.assert_schema_ready(settings.database_url_sync)

    container = await build_container(settings)

    if settings.auto_seed_dev_data:
        from ze_seed.context import SeedContext

        log.info("dev_seed_start")
        ctx = SeedContext.from_container(container)
        await container.dev_data_seeder.apply(ctx, force=True)
        log.info("dev_seed_done")

    app.state.settings = settings
    app.state.container = container
    mount_plugin_routers(app, container.plugins)

    log.info("ze_startup_complete", plugins=len(container.plugins))
    yield

    log.info("ze_shutdown")
    await container.close()
