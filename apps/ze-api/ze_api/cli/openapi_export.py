"""OpenAPI export with plugin REST routes included (for codegen)."""

from __future__ import annotations

import json

from ze_api.wiring.plugin_routes import collect_static_plugin_routers


def collect_openapi_operation_ids() -> frozenset[str]:
    """Return all operationId values from the exported OpenAPI schema."""
    schema = export_openapi()
    ids: set[str] = set()
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict):
                op_id = operation.get("operationId")
                if op_id:
                    ids.add(op_id)
    return frozenset(ids)


def export_openapi() -> dict:
    from ze_api.main import create_app

    app = create_app()
    for router in collect_static_plugin_routers():
        app.include_router(router)
    return app.openapi()


def main() -> None:
    print(json.dumps(export_openapi()))


if __name__ == "__main__":
    main()
