from __future__ import annotations

from types import SimpleNamespace

import pytest

from ze_api import migrate as ze_migrate
from ze_api.errors import MigrationReadinessError


class _FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


class _FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    def connect(self) -> _FakeConnection:
        return _FakeConnection()

    def dispose(self) -> None:
        self.disposed = True


def _patch_alembic_readiness(
    monkeypatch: pytest.MonkeyPatch,
    *,
    expected_heads: tuple[str, ...],
    current_heads: tuple[str, ...],
) -> _FakeEngine:
    engine = _FakeEngine()

    class FakeScriptDirectory:
        @classmethod
        def from_config(cls, cfg):
            return cls()

        def get_heads(self) -> tuple[str, ...]:
            return expected_heads

    class FakeMigrationContext:
        @staticmethod
        def configure(connection):
            return SimpleNamespace(get_current_heads=lambda: current_heads)

    def fake_engine_from_config(section, *, prefix, poolclass):
        assert section["sqlalchemy.url"] == "postgresql+psycopg2://test/test"
        assert prefix == "sqlalchemy."
        assert poolclass is ze_migrate.pool.NullPool
        return engine

    cfg = SimpleNamespace(
        config_ini_section="alembic",
        get_section=lambda name, default: {},
    )
    monkeypatch.setattr(ze_migrate, "_resolve_url", lambda database_url: database_url)
    monkeypatch.setattr(ze_migrate, "_build_config", lambda database_url: cfg)
    monkeypatch.setattr(ze_migrate, "ScriptDirectory", FakeScriptDirectory)
    monkeypatch.setattr(ze_migrate, "MigrationContext", FakeMigrationContext)
    monkeypatch.setattr(ze_migrate, "engine_from_config", fake_engine_from_config)
    return engine


def test_assert_schema_ready_passes_when_current_heads_match(monkeypatch):
    engine = _patch_alembic_readiness(
        monkeypatch,
        expected_heads=("head_a", "head_b"),
        current_heads=("head_b", "head_a"),
    )

    ze_migrate.assert_schema_ready("postgresql+psycopg2://test/test")

    assert engine.disposed is True


def test_assert_schema_ready_raises_when_heads_differ(monkeypatch):
    engine = _patch_alembic_readiness(
        monkeypatch,
        expected_heads=("head_a", "head_b"),
        current_heads=("head_a",),
    )

    with pytest.raises(MigrationReadinessError, match="Run `make migrate`"):
        ze_migrate.assert_schema_ready("postgresql+psycopg2://test/test")

    assert engine.disposed is True


def test_phase_165_revisions_join_the_discovered_chains():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = ze_migrate._build_config("postgresql+psycopg2://test/test")
    script = ScriptDirectory.from_config(cfg)
    zc031 = script.get_revision("zc031")
    zm024 = script.get_revision("zm024")
    assert zc031.down_revision == "zc030"
    assert zm024.down_revision == "zm023"
    assert isinstance(cfg, Config)
    heads = set(script.get_heads())
    assert {"zc035", "zm024"} <= heads
    assert "zc031" not in heads  # zc032 revises it (Phase 180)
    assert script.get_revision("zc035").down_revision == "zc034"
    assert script.get_revision("zc034").down_revision == "zc033"
    assert script.get_revision("zc033").down_revision == "zc032"
    assert script.get_revision("zc032").down_revision == "zc031"


def test_phase_180_revision_extends_the_core_chain():
    from alembic.script import ScriptDirectory

    cfg = ze_migrate._build_config("postgresql+psycopg2://test/test")
    script = ScriptDirectory.from_config(cfg)
    assert script.get_revision("zc032").down_revision == "zc031"


def test_phase_182_revision_extends_the_core_chain():
    from alembic.script import ScriptDirectory

    cfg = ze_migrate._build_config("postgresql+psycopg2://test/test")
    script = ScriptDirectory.from_config(cfg)
    assert script.get_revision("zc035").down_revision == "zc034"
    assert "zc034" not in set(script.get_heads())  # zc035 revises it (Phase 182)
    assert "zc035" in set(script.get_heads())
