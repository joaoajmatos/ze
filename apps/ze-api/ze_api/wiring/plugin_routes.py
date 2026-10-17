from __future__ import annotations

import importlib

from fastapi import FastAPI

from ze_api.errors import PluginRouteDriftError
from ze_logging import get_logger
from ze_plugin.bootstrap import load_plugin_classes

log = get_logger(__name__)


def collect_static_plugin_routers() -> list:
    """Import each plugin's route module without instantiating the plugin.

    The OpenAPI export and the runtime guard in `mount_plugin_routers` both read
    this list, so the generated client cannot describe routes the server lacks.
    """
    routers: list = []
    for _name, cls in load_plugin_classes():
        pkg = cls.__module__.rsplit(".", 1)[0]
        try:
            mod = importlib.import_module(f"{pkg}.api.routes")
        except ModuleNotFoundError:
            continue
        router = getattr(mod, "router", None)
        if router is not None:
            routers.append(router)
    return routers


def mount_plugin_routers(app: FastAPI, plugins: list) -> None:
    exported = collect_static_plugin_routers()
    for plugin in plugins:
        plugin_name = type(plugin).__name__
        routers = plugin.rest_routes()
        if not routers:
            continue
        for router in routers:
            if not any(router is known for known in exported):
                raise PluginRouteDriftError(
                    f"{plugin_name} mounts a router that is missing from the "
                    "OpenAPI export; export it from <package>.api.routes.router"
                )
        log.info(
            "plugin_rest_routes_registered",
            plugin=plugin_name,
            count=len(routers),
            prefixes=[router.prefix or "/" for router in routers],
        )
        for router in routers:
            app.include_router(router)
