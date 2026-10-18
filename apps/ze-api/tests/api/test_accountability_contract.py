"""Contract step for phase 194: the five surfaces are in the product OpenAPI."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ze_api.api import deps
from ze_api.cli.openapi_export import export_openapi

_SURFACES = {
    "listActionRecords": ("/api/v0/actions", "ActionRecordPage"),
    "listCollisions": ("/api/v0/collisions", "CollisionLogEntrySchema"),
    "getModelSettings": ("/api/v0/system/models", "ModelSettingsResponse"),
    "listChannelStatus": ("/api/v0/channels/status", "ChannelStatusResponse"),
}


def _operation(schema: dict, operation_id: str) -> dict:
    for path_item in schema["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and operation.get("operationId") == operation_id:
                return operation
    raise AssertionError(f"{operation_id} missing from the product OpenAPI")


@pytest.mark.parametrize("operation_id", sorted(_SURFACES))
def test_surface_is_in_the_product_spec(operation_id: str) -> None:
    schema = export_openapi()
    path, model = _SURFACES[operation_id]
    assert path in schema["paths"]
    operation = _operation(schema, operation_id)
    assert model in str(operation["responses"]["200"])
    assert operation["summary"]
    assert operation["description"]


def test_list_loops_accepts_since_and_repeatable_state() -> None:
    operation = _operation(export_openapi(), "listLoops")
    params = {p["name"]: p for p in operation["parameters"]}
    assert "since" in params
    assert params["state"]["schema"]["anyOf"][0]["type"] == "array"


def test_list_action_records_params() -> None:
    operation = _operation(export_openapi(), "listActionRecords")
    names = {p["name"] for p in operation["parameters"]}
    assert names == {"subject_type", "subject_id", "since", "cursor", "limit"}


@pytest.mark.parametrize(
    ("getter", "field"),
    [
        (deps.get_action_record_store, "action_record_store"),
        (deps.get_user_channel_store, "user_channel_store"),
        (deps.get_watermark_store, "watermark_store"),
        (deps.get_channel_registry, "channel_registry"),
    ],
)
def test_getter_resolves_from_the_container(getter, field: str) -> None:
    sentinel = object()
    container = SimpleNamespace(**{field: sentinel})
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(container=container)))
    assert getter(request) is sentinel


def test_container_has_the_new_fields_and_no_reset_service() -> None:
    from dataclasses import fields

    from ze_api.wiring.container import ZeContainer

    names = {f.name for f in fields(ZeContainer)}
    assert {"action_record_store", "user_channel_store", "watermark_store"} <= names
    assert "reset_service" not in names
