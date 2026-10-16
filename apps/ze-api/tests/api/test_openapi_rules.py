"""OpenAPI rules every REST route follows (AGENTS.md "OpenAPI")."""

from __future__ import annotations

import re

import pytest

from ze_api.api.app import create_app
from ze_api.openapi_export import export_openapi
from ze_api.settings import get_settings

_CAMEL_CASE = re.compile(r"^[a-z][a-zA-Z0-9]*$")
_SUCCESS = ("200", "201", "202")


@pytest.fixture(scope="module")
def schema() -> dict:
    return export_openapi()


@pytest.fixture(scope="module")
def eval_schema() -> dict:
    import os

    os.environ["EVAL_MODE"] = "true"
    get_settings.cache_clear()
    try:
        return create_app().openapi()
    finally:
        del os.environ["EVAL_MODE"]
        get_settings.cache_clear()


def _operations(schema: dict):
    for path, item in schema["paths"].items():
        for method, op in item.items():
            yield method.upper(), path, op


def test_operation_ids_are_camel_case(schema, eval_schema):
    bad = [
        f"{method} {path} -> {op.get('operationId')}"
        for s in (schema, eval_schema)
        for method, path, op in _operations(s)
        if not _CAMEL_CASE.match(op.get("operationId", ""))
    ]
    assert not bad


def test_every_operation_has_summary_and_description(schema, eval_schema):
    bad = [
        f"{method} {path}"
        for s in (schema, eval_schema)
        for method, path, op in _operations(s)
        if not (op.get("summary") and op.get("description"))
    ]
    assert not bad


def test_every_rest_route_lives_under_api_v0(schema):
    assert not [p for p in schema["paths"] if not p.startswith("/api/v0/")]


def test_json_success_responses_carry_a_schema(schema, eval_schema):
    bad = []
    for s in (schema, eval_schema):
        for method, path, op in _operations(s):
            for code in _SUCCESS:
                content = op.get("responses", {}).get(code, {}).get("content", {})
                body = content.get("application/json")
                if body is not None and not body.get("schema"):
                    bad.append(f"{method} {path} {code}")
    assert not bad


@pytest.mark.parametrize(
    ("method", "path", "media_type"),
    [
        ("get", "/api/v0/data/export", "application/zip"),
        ("get", "/api/v0/workspace/files/{file_path}", "application/octet-stream"),
        ("get", "/api/v0/workspace/runs/{run_id}/events", "application/x-ndjson"),
    ],
)
def test_streamed_responses_document_their_media_type(schema, method, path, media_type):
    ok = schema["paths"][path][method]["responses"]["200"]
    assert list(ok["content"]) == [media_type]
