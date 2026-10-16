"""Tests for telemetry: CostContext, CostStore, CostTracker, CostReconciler."""

import asyncio
from contextvars import copy_context
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ze_core.telemetry.context import (
    CostContext,
    get_cost_context,
    set_agent_context,
    set_flow_context,
    start_flow_context,
    enter_turn_context,
)
from ze_core.telemetry.postgres import PostgresCostStore
from ze_core.telemetry.reconciler import CostReconciler
from ze_core.telemetry.sqlite import SQLiteCostStore
from ze_core.telemetry.store import CostStore
from ze_core.telemetry.tracker import CostTracker
from ze_core.telemetry.types import CostRecord, UsageInfo


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_pool(rows=None):
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=rows or [])
    conn.execute = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=cm)
    return pool, conn


def _make_rec(**kwargs) -> CostRecord:
    defaults = dict(
        agent="a",
        flow_type="f",
        model="m",
        prompt_tokens=1,
        completion_tokens=2,
        total_tokens=3,
        duration_ms=100,
        session_id=None,
        cost_usd=None,
        generation_id=None,
    )
    return CostRecord(**{**defaults, **kwargs})


# ── TestCostContext ───────────────────────────────────────────────────────────


class TestCostContext:
    def test_get_returns_default_when_unset(self):
        ctx = get_cost_context()
        assert ctx.flow_type == "unknown"
        assert ctx.agent == "unknown"
        assert ctx.session_id is None

    def test_set_flow_context_creates_entry(self):
        def _run():
            set_flow_context("research", session_id="s1")
            ctx = get_cost_context()
            assert ctx.flow_type == "research"
            assert ctx.session_id == "s1"
            assert ctx.agent == "unknown"

        copy_context().run(_run)

    def test_set_agent_context_updates_agent(self):
        def _run():
            set_flow_context("companion")
            set_agent_context("companion_agent")
            ctx = get_cost_context()
            assert ctx.agent == "companion_agent"
            assert ctx.flow_type == "companion"

        copy_context().run(_run)

    def test_set_agent_context_without_flow_still_attributes_agent(self):
        def _run():
            set_agent_context("orphan")
            ctx = get_cost_context()
            assert ctx.flow_type == "unknown"
            assert ctx.agent == "orphan"

        copy_context().run(_run)

    def test_start_flow_context_replaces_everything(self):
        def _run():
            set_flow_context("old", session_id="s0")
            set_agent_context("stale_agent")
            start_flow_context("user_message", session_id="thread-1")
            ctx = get_cost_context()
            assert ctx.flow_type == "user_message"
            assert ctx.session_id == "thread-1"
            assert ctx.agent == "unknown"

        copy_context().run(_run)

    def test_enter_turn_context_starts_user_message_flow(self):
        def _run():
            enter_turn_context("thread-9")
            ctx = get_cost_context()
            assert (ctx.flow_type, ctx.session_id) == ("user_message", "thread-9")

        copy_context().run(_run)

    def test_enter_turn_context_restarts_for_the_next_thread(self):
        def _run():
            enter_turn_context("a")
            set_agent_context("router")
            enter_turn_context("b")
            ctx = get_cost_context()
            assert (ctx.session_id, ctx.agent) == ("b", "unknown")

        copy_context().run(_run)

    def test_enter_turn_context_keeps_an_outer_flow(self):
        def _run():
            set_flow_context("eval", session_id="eval-1")
            enter_turn_context("thread-9")
            ctx = get_cost_context()
            assert (ctx.flow_type, ctx.session_id) == ("eval", "eval-1")

        copy_context().run(_run)

    async def test_child_task_inherits_flow_and_sets_its_own_agent(self):
        async def _child():
            set_agent_context("router")
            return get_cost_context()

        start_flow_context("user_message", session_id="t1")
        child_ctx = await asyncio.create_task(_child())
        assert child_ctx.flow_type == "user_message"
        assert child_ctx.session_id == "t1"
        assert child_ctx.agent == "router"
        assert get_cost_context().agent == "unknown"

    def test_set_flow_context_preserves_agent(self):
        def _run():
            set_flow_context("flow1")
            set_agent_context("agent1")
            set_flow_context("flow2", session_id="s2")
            ctx = get_cost_context()
            assert ctx.flow_type == "flow2"
            assert ctx.agent == "agent1"
            assert ctx.session_id == "s2"

        copy_context().run(_run)

    def test_context_is_frozen(self):
        ctx = CostContext(flow_type="f", agent="a")
        with pytest.raises(Exception):
            ctx.flow_type = "x"  # type: ignore[misc]

    def test_context_isolation_between_tasks(self):
        results = {}

        def _task_a():
            set_flow_context("flow-a")
            results["a"] = get_cost_context().flow_type

        def _task_b():
            set_flow_context("flow-b")
            results["b"] = get_cost_context().flow_type

        copy_context().run(_task_a)
        copy_context().run(_task_b)
        assert results["a"] == "flow-a"
        assert results["b"] == "flow-b"


# ── TestCostStore (Protocol) ──────────────────────────────────────────────────


class TestCostStoreProtocol:
    def test_postgres_store_satisfies_protocol(self):
        pool, _ = _make_pool()
        store = PostgresCostStore(pool)
        assert isinstance(store, CostStore)

    async def test_sqlite_store_satisfies_protocol(self):
        store = SQLiteCostStore(":memory:")
        await store.setup()
        assert isinstance(store, CostStore)
        await store.aclose()


# ── TestPostgresCostStore ─────────────────────────────────────────────────────


class TestPostgresCostStore:
    async def test_write_executes_insert(self):
        pool, conn = _make_pool()
        store = PostgresCostStore(pool)
        await store.write(_make_rec())
        conn.execute.assert_awaited_once()
        sql = conn.execute.call_args[0][0]
        assert "INSERT INTO llm_cost_log" in sql

    async def test_write_swallows_db_error(self):
        pool, conn = _make_pool()
        conn.execute = AsyncMock(side_effect=Exception("db down"))
        store = PostgresCostStore(pool)
        await store.write(_make_rec())  # must not raise

    async def test_fetch_pending_returns_rows(self):
        rows = [{"id": "r1", "generation_id": "gen-1"}]
        pool, conn = _make_pool(rows)
        store = PostgresCostStore(pool)
        result = await store.fetch_pending(
            batch_size=50, min_age_seconds=120, max_age_seconds=86400
        )
        assert result == rows

    async def test_fetch_pending_takes_newest_first_inside_a_recency_window(self):
        pool, conn = _make_pool([])
        store = PostgresCostStore(pool)
        await store.fetch_pending(
            batch_size=50, min_age_seconds=120, max_age_seconds=3 * 86400
        )
        sql, *args = conn.fetch.call_args[0]
        assert "ORDER BY created_at DESC" in sql
        assert "created_at >" in sql
        assert 120 in args and 3 * 86400 in args and 50 in args

    async def test_fetch_pending_excludes_known_unavailable_generations(self):
        pool, conn = _make_pool([])
        store = PostgresCostStore(pool)
        await store.fetch_pending(
            batch_size=50,
            min_age_seconds=120,
            max_age_seconds=86400,
            exclude_generation_ids=["gen-dead"],
        )
        sql, *args = conn.fetch.call_args[0]
        assert "generation_id <> ALL" in sql
        assert ["gen-dead"] in args

    async def test_update_cost_reports_whether_a_row_changed(self):
        pool, conn = _make_pool()
        conn.execute = AsyncMock(return_value="UPDATE 1")
        store = PostgresCostStore(pool)
        assert await store.update_cost("row-1", 0.01) is True
        conn.execute = AsyncMock(return_value="UPDATE 0")
        assert await store.update_cost("row-1", 0.01) is False

    async def test_update_cost_executes_update(self):
        pool, conn = _make_pool()
        store = PostgresCostStore(pool)
        await store.update_cost("row-1", 0.0042)
        conn.execute.assert_awaited_once()
        call_args = conn.execute.call_args[0]
        assert 0.0042 in call_args
        assert "row-1" in call_args

    async def test_fetch_session_usage_queries_by_session_id(self):
        rows = [{"model": "m1", "prompt_tokens": 10, "completion_tokens": 5}]
        pool, conn = _make_pool(rows)
        store = PostgresCostStore(pool)
        result = await store.fetch_session_usage("s1")
        assert result == rows
        sql = conn.fetch.call_args[0][0]
        assert "session_id = $1" in sql

    async def test_fetch_daily_usage_queries_by_current_date(self):
        rows = [{"model": "m1", "prompt_tokens": 10, "completion_tokens": 5}]
        pool, conn = _make_pool(rows)
        store = PostgresCostStore(pool)
        result = await store.fetch_daily_usage()
        assert result == rows
        sql = conn.fetch.call_args[0][0]
        assert "CURRENT_DATE" in sql


# ── TestSQLiteCostStore ───────────────────────────────────────────────────────


class TestSQLiteCostStore:
    async def test_setup_creates_table(self):
        store = SQLiteCostStore(":memory:")
        await store.setup()
        async with store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='llm_cost_log'"
        ) as cur:
            row = await cur.fetchone()
        assert row is not None
        await store.aclose()

    async def test_write_stores_record(self):
        store = SQLiteCostStore(":memory:")
        await store.setup()
        await store.write(_make_rec(model="test-model", total_tokens=42))
        async with store._conn.execute("SELECT COUNT(*) FROM llm_cost_log") as cur:
            count = (await cur.fetchone())[0]
        assert count == 1
        await store.aclose()

    async def test_write_stores_correct_values(self):
        store = SQLiteCostStore(":memory:")
        await store.setup()
        rec = _make_rec(
            model="my-model", agent="researcher", total_tokens=99, generation_id="gen-x"
        )
        await store.write(rec)
        async with store._conn.execute(
            "SELECT model, agent, total_tokens, generation_id FROM llm_cost_log"
        ) as cur:
            row = await cur.fetchone()
        assert row["model"] == "my-model"
        assert row["agent"] == "researcher"
        assert row["total_tokens"] == 99
        assert row["generation_id"] == "gen-x"
        await store.aclose()

    async def test_aclose_sets_conn_none(self):
        store = SQLiteCostStore(":memory:")
        await store.setup()
        await store.aclose()
        assert store._conn is None

    async def test_double_close_is_safe(self):
        store = SQLiteCostStore(":memory:")
        await store.setup()
        await store.aclose()
        await store.aclose()  # must not raise

    async def test_write_before_setup_logs_warning(self):
        store = SQLiteCostStore(":memory:")
        await store.write(_make_rec())  # must not raise

    async def test_fetch_session_usage_returns_matching_rows(self):
        store = SQLiteCostStore(":memory:")
        await store.setup()
        await store.write(_make_rec(session_id="s1", model="m1", prompt_tokens=10))
        await store.write(_make_rec(session_id="s2", model="m2", prompt_tokens=20))
        rows = await store.fetch_session_usage("s1")
        assert len(rows) == 1
        assert rows[0]["model"] == "m1"
        assert rows[0]["prompt_tokens"] == 10
        await store.aclose()

    async def test_fetch_session_usage_before_setup_returns_empty(self):
        store = SQLiteCostStore(":memory:")
        rows = await store.fetch_session_usage("s1")
        assert rows == []

    async def test_fetch_daily_usage_returns_todays_rows(self):
        store = SQLiteCostStore(":memory:")
        await store.setup()
        await store.write(_make_rec(model="today-model", prompt_tokens=5))
        rows = await store.fetch_daily_usage()
        assert len(rows) == 1
        assert rows[0]["model"] == "today-model"
        await store.aclose()

    async def test_fetch_daily_usage_before_setup_returns_empty(self):
        store = SQLiteCostStore(":memory:")
        rows = await store.fetch_daily_usage()
        assert rows == []


# ── TestCostTracker ───────────────────────────────────────────────────────────


class TestCostTracker:
    def test_record_without_store_does_not_raise(self):
        tracker = CostTracker(store=None)
        tracker.record(
            model="m",
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
            duration_ms=50,
        )

    async def test_record_with_store_creates_task(self):
        store = AsyncMock(spec=CostStore)
        tracker = CostTracker(store=store)
        created = []
        with patch(
            "asyncio.create_task",
            side_effect=lambda coro: created.append(coro) or MagicMock(),
        ):
            tracker.record(
                model="m",
                prompt_tokens=1,
                completion_tokens=2,
                total_tokens=3,
                duration_ms=50,
            )
        assert len(created) == 1

    async def test_record_calls_store_write(self):
        store = AsyncMock(spec=CostStore)
        tracker = CostTracker(store=store)
        with patch("asyncio.create_task", lambda coro: asyncio.ensure_future(coro)):
            tracker.record(
                model="m",
                prompt_tokens=1,
                completion_tokens=2,
                total_tokens=3,
                duration_ms=50,
            )
        await asyncio.sleep(0)
        store.write.assert_awaited_once()
        rec = store.write.call_args[0][0]
        assert rec.model == "m"
        assert rec.total_tokens == 3

    async def test_record_captures_cost_context(self):
        store = AsyncMock(spec=CostStore)
        tracker = CostTracker(store=store)
        set_flow_context("research", session_id="sess-1")
        set_agent_context("researcher")
        with patch("asyncio.create_task", lambda coro: asyncio.ensure_future(coro)):
            tracker.record("m", 1, 2, 3, 10)
        await asyncio.sleep(0)
        rec = store.write.call_args[0][0]
        assert rec.flow_type == "research"
        assert rec.agent == "researcher"
        assert rec.session_id == "sess-1"

    def test_record_audio_seconds(self):
        tracker = CostTracker(store=None)
        tracker.record(
            model="whisper",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            duration_ms=200,
            audio_seconds=12.5,
        )


# ── TestCostReconciler ────────────────────────────────────────────────────────


class TestCostReconciler:
    async def test_skips_db_when_no_pending_writes(self):
        store = AsyncMock(spec=PostgresCostStore)
        store.has_pending_writes = False
        client = AsyncMock()
        reconciler = CostReconciler(store=store, openrouter_client=client)
        await reconciler.run()
        store.fetch_pending.assert_not_awaited()
        client.fetch_generation_cost.assert_not_awaited()

    async def test_no_rows_marks_clean_and_returns_early(self):
        store = AsyncMock(spec=PostgresCostStore)
        store.has_pending_writes = True
        store.fetch_pending = AsyncMock(return_value=[])
        client = AsyncMock()
        reconciler = CostReconciler(store=store, openrouter_client=client)
        await reconciler.run()
        store.mark_clean.assert_called_once()
        client.fetch_generation_cost.assert_not_awaited()

    async def test_fetches_cost_and_updates_row(self):
        row = {"id": "row-1", "generation_id": "gen-abc"}
        store = AsyncMock(spec=PostgresCostStore)
        store.fetch_pending = AsyncMock(return_value=[row])
        store.update_cost = AsyncMock()
        client = AsyncMock()
        client.fetch_generation_cost = AsyncMock(return_value=0.0042)
        reconciler = CostReconciler(store=store, openrouter_client=client)
        await reconciler.run()
        client.fetch_generation_cost.assert_awaited_once_with("gen-abc")
        store.update_cost.assert_awaited_once_with("row-1", 0.0042)

    async def test_skips_row_when_cost_unavailable(self):
        row = {"id": "row-2", "generation_id": "gen-xyz"}
        store = AsyncMock(spec=PostgresCostStore)
        store.fetch_pending = AsyncMock(return_value=[row])
        store.update_cost = AsyncMock()
        client = AsyncMock()
        client.fetch_generation_cost = AsyncMock(return_value=None)
        reconciler = CostReconciler(store=store, openrouter_client=client)
        await reconciler.run()
        store.update_cost.assert_not_awaited()

    async def test_processes_multiple_rows(self):
        rows = [{"id": f"r{i}", "generation_id": f"gen-{i}"} for i in range(3)]
        store = AsyncMock(spec=PostgresCostStore)
        store.fetch_pending = AsyncMock(return_value=rows)
        store.update_cost = AsyncMock()
        client = AsyncMock()
        client.fetch_generation_cost = AsyncMock(return_value=0.001)
        reconciler = CostReconciler(store=store, openrouter_client=client)
        await reconciler.run()
        assert client.fetch_generation_cost.await_count == 3
        assert store.update_cost.await_count == 3


class TestCostReconcilerRetryCap:
    async def test_invalid_generation_id_is_not_asked_again(self):
        """HTTP 400 'Invalid generation ID' is permanent: blacklisted at once."""
        from ze_agents.errors import GenerationUnavailableError

        dead = {"id": "r-dead", "generation_id": "gen-dead"}
        live = {"id": "r-live", "generation_id": "gen-live"}
        store = AsyncMock(spec=PostgresCostStore)
        store.has_pending_writes = True
        store.fetch_pending = AsyncMock(return_value=[dead, live])
        store.update_cost = AsyncMock(return_value=True)
        client = AsyncMock()

        async def _cost(gid):
            if gid == "gen-dead":
                raise GenerationUnavailableError("bad id", status_code=400)
            return 0.001

        client.fetch_generation_cost = AsyncMock(side_effect=_cost)
        reconciler = CostReconciler(store=store, openrouter_client=client)

        await reconciler.run()
        store.update_cost.assert_awaited_once_with("r-live", 0.001)

        await reconciler.run()
        kwargs = store.fetch_pending.call_args.kwargs
        assert "gen-dead" in kwargs["exclude_generation_ids"]

    async def test_a_404_is_retried_before_it_is_given_up_on(self):
        """OpenRouter answers 404 for a generation it has not indexed yet, so one miss
        must not blacklist the row for the process."""
        from ze_agents.errors import GenerationUnavailableError

        row = {"id": "r1", "generation_id": "gen-slow"}
        store = AsyncMock(spec=PostgresCostStore)
        store.has_pending_writes = True
        store.fetch_pending = AsyncMock(return_value=[row])
        store.update_cost = AsyncMock(return_value=True)
        client = AsyncMock()
        client.fetch_generation_cost = AsyncMock(
            side_effect=[
                GenerationUnavailableError("not yet", status_code=404),
                GenerationUnavailableError("not yet", status_code=404),
                0.002,
            ]
        )
        reconciler = CostReconciler(store=store, openrouter_client=client)

        await reconciler.run()
        await reconciler.run()
        assert (
            "gen-slow"
            not in store.fetch_pending.call_args.kwargs["exclude_generation_ids"]
        )
        await reconciler.run()

        store.update_cost.assert_awaited_once_with("r1", 0.002)

    async def test_a_404_is_given_up_on_after_three_misses(self):
        from ze_agents.errors import GenerationUnavailableError

        row = {"id": "r1", "generation_id": "gen-gone"}
        store = AsyncMock(spec=PostgresCostStore)
        store.has_pending_writes = True
        store.fetch_pending = AsyncMock(return_value=[row])
        client = AsyncMock()
        client.fetch_generation_cost = AsyncMock(
            side_effect=GenerationUnavailableError("gone", status_code=404)
        )
        reconciler = CostReconciler(store=store, openrouter_client=client)

        for _ in range(3):
            await reconciler.run()
        await reconciler.run()

        assert (
            "gen-gone" in store.fetch_pending.call_args.kwargs["exclude_generation_ids"]
        )

    async def test_a_resolved_row_forgets_its_misses(self):
        from ze_agents.errors import GenerationUnavailableError

        row = {"id": "r1", "generation_id": "gen-x"}
        store = AsyncMock(spec=PostgresCostStore)
        store.has_pending_writes = True
        store.fetch_pending = AsyncMock(return_value=[row])
        store.update_cost = AsyncMock(return_value=False)  # row stays pending
        client = AsyncMock()
        not_found = GenerationUnavailableError("nf", status_code=404)
        client.fetch_generation_cost = AsyncMock(
            side_effect=[not_found, not_found, 0.1, not_found, not_found]
        )
        reconciler = CostReconciler(store=store, openrouter_client=client)

        for _ in range(5):
            await reconciler.run()

        # 2 misses, a success, 2 more misses: never 3 in a row
        assert (
            "gen-x"
            not in store.fetch_pending.call_args.kwargs["exclude_generation_ids"]
        )

    async def test_one_unavailable_row_does_not_stop_the_batch(self):
        from ze_agents.errors import GenerationUnavailableError

        rows = [{"id": f"r{i}", "generation_id": f"gen-{i}"} for i in range(3)]
        store = AsyncMock(spec=PostgresCostStore)
        store.has_pending_writes = True
        store.fetch_pending = AsyncMock(return_value=rows)
        store.update_cost = AsyncMock(return_value=True)
        client = AsyncMock()
        client.fetch_generation_cost = AsyncMock(
            side_effect=[GenerationUnavailableError("x"), 0.1, 0.2]
        )
        await CostReconciler(store=store, openrouter_client=client).run()
        assert store.update_cost.await_count == 2

    async def test_update_that_changes_no_row_is_not_counted(self):
        row = {"id": "r1", "generation_id": "gen-1"}
        store = AsyncMock(spec=PostgresCostStore)
        store.has_pending_writes = True
        store.fetch_pending = AsyncMock(return_value=[row])
        store.update_cost = AsyncMock(return_value=False)
        client = AsyncMock()
        client.fetch_generation_cost = AsyncMock(return_value=0.1)
        with patch("ze_core.telemetry.reconciler.log") as log:
            await CostReconciler(store=store, openrouter_client=client).run()
        done = [
            c for c in log.info.call_args_list if c.args[0] == "cost_reconcile_done"
        ]
        assert done[0].kwargs["updated"] == 0
        log.warning.assert_called()

    async def test_fetch_uses_the_recency_window(self):
        store = AsyncMock(spec=PostgresCostStore)
        store.has_pending_writes = True
        store.fetch_pending = AsyncMock(return_value=[])
        await CostReconciler(store=store, openrouter_client=AsyncMock()).run()
        kwargs = store.fetch_pending.call_args.kwargs
        assert kwargs["max_age_seconds"] == 3 * 86400


# ── TestUsageInfo ─────────────────────────────────────────────────────────────


class TestUsageInfo:
    def test_fields(self):
        u = UsageInfo(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            generation_id="gen-1",
            duration_ms=150,
        )
        assert u.total_tokens == 30
        assert u.generation_id == "gen-1"
