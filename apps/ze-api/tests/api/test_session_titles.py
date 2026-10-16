from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from ze_api.api.websocket.session_titles import _title_generator


def _container(config: dict) -> SimpleNamespace:
    settings = SimpleNamespace(config=config)
    return SimpleNamespace(settings=settings, openrouter_client=MagicMock())


class TestTitleGenerator:
    def test_uses_declared_default_when_no_override(self):
        container = _container(
            {"models": {"default": "fleet-default", "overrides": {}}}
        )
        generator = _title_generator(container)
        assert generator._model == "anthropic/claude-haiku-4-5"

    def test_override_pins_session_title_model(self):
        container = _container(
            {
                "models": {
                    "default": "fleet-default",
                    "overrides": {"session_title": "pinned-model"},
                }
            }
        )
        generator = _title_generator(container)
        assert generator._model == "pinned-model"


class TestTitleOnlyUntilItExists:
    """The first user message is saved as a 60-character placeholder with title_source
    'user' before the turn runs (turns.py), so a generated title must replace that
    placeholder exactly once."""

    @staticmethod
    def _session(title=None, title_source=None):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        return SimpleNamespace(
            id="t1",
            title=title,
            preview=None,
            title_source=title_source,
            created_at=now,
            last_active_at=now,
        )

    async def _run(self, session):
        from unittest.mock import AsyncMock, patch

        from ze_api.api.websocket import session_titles

        store = MagicMock()
        store.get = AsyncMock(return_value=session)
        store.upsert = AsyncMock()
        generate = AsyncMock(return_value="A title")
        with patch.object(session_titles.SessionTitleGenerator, "generate", generate):
            await session_titles._generate_and_save(
                _container({"models": {}}), store, "t1", "hello", "hi there"
            )
        return generate, store

    async def test_replaces_the_placeholder_the_first_message_saved(self):
        session = self._session("first 60 chars of the message", "user")
        generate, store = await self._run(session)
        generate.assert_awaited_once()
        store.upsert.assert_awaited_once()
        assert store.upsert.await_args.kwargs["title"] == "A title"
        assert store.upsert.await_args.kwargs["title_source"] == "generated"

    async def test_generates_when_the_session_has_no_title(self):
        generate, store = await self._run(self._session())
        generate.assert_awaited_once()
        store.upsert.assert_awaited_once()

    async def test_skips_once_a_title_was_generated(self):
        generate, store = await self._run(self._session("T", "generated"))
        generate.assert_not_awaited()
        store.upsert.assert_not_awaited()

    async def test_skips_a_missing_session(self):
        generate, store = await self._run(None)
        generate.assert_not_awaited()

    async def test_title_calls_are_attributed_to_session_title(self):
        from ze_core.telemetry.context import get_cost_context

        seen = []

        async def _generate(self, **kwargs):
            seen.append(get_cost_context().agent)
            return "A title"

        from unittest.mock import AsyncMock, patch

        from ze_api.api.websocket import session_titles

        store = MagicMock()
        store.get = AsyncMock(return_value=self._session())
        store.upsert = AsyncMock()
        with patch.object(session_titles.SessionTitleGenerator, "generate", _generate):
            await session_titles._generate_and_save(
                _container({"models": {}}), store, "t1", "hello", "hi"
            )
        assert seen == ["session_title"]
