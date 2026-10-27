from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, create_autospec

from ze_personal.contacts.types import StaleFollowUpNudge
from ze_personal.jobs.briefing import MorningBriefing
from ze_personal.push_kinds import MORNING_BRIEF
from ze_sdk.memory import PostgresMemoryStore
from ze_agents.settings import Settings
from ze_sdk.proactive import OncePer, ProactiveNotifier
from ze_automation.workflow.types import WorkflowFailure
from ze_news.types import Article


def make_settings():
    return Settings(
        openrouter_api_key="test-key",
        database_url="postgresql://ze:ze@localhost:5432/ze",
    )


def make_notifier(outcome="delivered"):
    n = MagicMock(spec=ProactiveNotifier)
    n.notify = AsyncMock(return_value=outcome)
    n.on_cooldown = AsyncMock(return_value=False)
    return n


def make_priority_view(stale_contacts=None):
    items = [
        SimpleNamespace(source_kind="relationship", signal=nudge)
        for nudge in (stale_contacts or [])
    ]
    priority_view = MagicMock()
    priority_view.rank = AsyncMock(return_value=SimpleNamespace(items=items))
    return priority_view


def make_briefing(
    *,
    dedup=False,
    unreviewed=0,
    workflows=None,
    failures=None,
    stale_contacts=None,
    notifier=None,
    settings=None,
    news_store=None,
    memory_store=None,
    priority_view=None,
):
    notifier = notifier or make_notifier()
    notifier.on_cooldown = AsyncMock(return_value=dedup)

    memory = memory_store or MagicMock()
    if memory_store is None:
        memory.count_unreviewed_facts = AsyncMock(return_value=unreviewed)
    if not hasattr(memory, "list_recent_facts"):
        memory.list_recent_facts = AsyncMock(return_value=[])
    if not hasattr(memory, "get_profile"):
        memory.get_profile = AsyncMock(return_value=[])

    workflow_store = MagicMock()
    workflow_store.list_enabled_scheduled = AsyncMock(return_value=workflows or [])
    workflow_store.list_failed_executions = AsyncMock(return_value=failures or [])

    b = MorningBriefing(
        notifier=notifier,
        memory_store=memory,
        workflow_store=workflow_store,
        settings=settings or make_settings(),
        news_store=news_store,
        priority_view=priority_view or make_priority_view(stale_contacts),
    )
    return b, workflow_store


async def test_briefing_sends_stats():
    notifier = make_notifier()
    w = MagicMock()
    w.name = "daily_report"
    workflows = [w]
    b, _ = make_briefing(unreviewed=2, workflows=workflows, notifier=notifier)
    await b.run()

    notifier.notify.assert_awaited_once()
    assert notifier.notify.call_args[0][0] is MORNING_BRIEF
    text = notifier.notify.call_args[0][2]
    assert "Good morning" in text
    assert "Unreviewed facts: 2" in text
    assert "daily_report" in text


async def test_briefing_dedup_skips():
    notifier = make_notifier()
    b, workflow_store = make_briefing(dedup=True, notifier=notifier)
    await b.run()
    notifier.on_cooldown.assert_awaited_once_with(
        OncePer("morning_brief", within=timedelta(hours=20))
    )
    notifier.notify.assert_not_awaited()
    workflow_store.list_failed_executions.assert_not_awaited()


async def test_briefing_includes_nudge_above_threshold():
    notifier = make_notifier()
    b, _ = make_briefing(unreviewed=6, notifier=notifier)
    await b.run()

    text = notifier.notify.call_args[0][2]
    assert "waiting for review" in text


async def test_briefing_no_nudge_below_threshold():
    notifier = make_notifier()
    b, _ = make_briefing(unreviewed=2, notifier=notifier)
    await b.run()

    text = notifier.notify.call_args[0][2]
    assert "waiting for review" not in text


async def test_briefing_includes_failure_summary():
    notifier = make_notifier()
    failures = [
        WorkflowFailure(
            workflow_id=uuid4(),
            workflow_name="daily_report",
            execution_id=uuid4(),
            failed_at=datetime(2026, 5, 20, 2, 0, tzinfo=timezone.utc),
            error="boom",
        )
    ]
    b, workflow_store = make_briefing(failures=failures, notifier=notifier)
    await b.run()

    workflow_store.list_failed_executions.assert_awaited_once_with(24)
    text = notifier.notify.call_args[0][2]
    assert "Recent failure: daily_report at 02:00 UTC" in text


async def test_briefing_lists_every_failure_of_one_workflow():
    """Two failed runs of one workflow both appear, alerted or not (US3, SC-004)."""
    wid = uuid4()
    failures = [
        WorkflowFailure(
            wid,
            "daily_report",
            uuid4(),
            datetime(2026, 5, 20, h, 0, tzinfo=timezone.utc),
            "x",
        )
        for h in (6, 2)
    ]
    notifier = make_notifier()
    b, _ = make_briefing(failures=failures, notifier=notifier)
    await b.run()

    text = notifier.notify.call_args[0][2]
    assert text.count("Recent failure: daily_report") == 2
    assert "at 06:00 UTC" in text and "at 02:00 UTC" in text


async def test_briefing_notifies_once_per_morning_brief():
    notifier = make_notifier()
    b, _ = make_briefing(notifier=notifier)
    await b.run()

    assert notifier.notify.call_args.kwargs["once_per"] == OncePer(
        "morning_brief", within=timedelta(hours=20)
    )


async def test_briefing_calls_memory_store_real_interface():
    """The job runs against `PostgresMemoryStore`'s real interface. The mock is
    autospecced on the store class, so a call to a method the store does not
    define fails — the regression guard for `count_unreviewed_facts`, which the
    briefing relied on but the store lost in the ze_memory extraction."""
    notifier = make_notifier()
    memory = create_autospec(PostgresMemoryStore, instance=True)
    memory.count_unreviewed_facts.return_value = 3

    b, _ = make_briefing(notifier=notifier, memory_store=memory)
    await b.run()

    notifier.notify.assert_awaited_once()
    text = notifier.notify.call_args[0][2]
    assert "Unreviewed facts: 3" in text
    memory.count_unreviewed_facts.assert_awaited_once()


async def test_briefing_includes_stale_contact_nudge():
    notifier = make_notifier()
    stale = [StaleFollowUpNudge(name="João Silva", days_ago=14)]
    b, _ = make_briefing(stale_contacts=stale, notifier=notifier)
    await b.run()

    text = notifier.notify.call_args[0][2]
    assert "Follow-up nudges" in text
    assert "João Silva" in text
    assert "14 days ago" in text


async def test_briefing_no_nudge_when_no_stale_contacts():
    notifier = make_notifier()
    b, _ = make_briefing(stale_contacts=[], notifier=notifier)
    await b.run()

    text = notifier.notify.call_args[0][2]
    assert "Follow-up nudges" not in text


async def test_briefing_singular_day_in_nudge():
    notifier = make_notifier()
    stale = [StaleFollowUpNudge(name="Ana Costa", days_ago=1)]
    b, _ = make_briefing(stale_contacts=stale, notifier=notifier)
    await b.run()

    text = notifier.notify.call_args[0][2]
    assert "1 day ago" in text
    assert "1 days ago" not in text


async def test_briefing_reads_relationship_nudges_from_priority_view_not_person_store():
    """SC-003: the stale-relationship line comes from PriorityView's ranked
    output, not a direct PersonStore.list_stale_for_follow_up() call."""
    notifier = make_notifier()
    priority_view = make_priority_view(
        [StaleFollowUpNudge(name="Rui Pereira", days_ago=21)]
    )
    b, _ = make_briefing(notifier=notifier, priority_view=priority_view)
    await b.run()

    priority_view.rank.assert_awaited_once()
    text = notifier.notify.call_args[0][2]
    assert "Rui Pereira" in text
    assert "21 days ago" in text


async def test_briefing_ignores_non_relationship_priority_items():
    notifier = make_notifier()
    priority_view = MagicMock()
    priority_view.rank = AsyncMock(
        return_value=SimpleNamespace(
            items=[SimpleNamespace(source_kind="loop", signal=object())]
        )
    )
    b, _ = make_briefing(notifier=notifier, priority_view=priority_view)
    await b.run()

    text = notifier.notify.call_args[0][2]
    assert "Follow-up nudges" not in text


async def test_briefing_includes_headlines_when_news_store_present():
    notifier = make_notifier()
    articles = [
        Article(
            url="https://bbc.com/1",
            source_key="bbc_world",
            title="Global Summit Concludes",
            summary="Leaders reached an agreement.",
            published_at=datetime(2026, 6, 7, 8, 0, tzinfo=timezone.utc),
            tags=["global"],
        ),
        Article(
            url="https://bbc.com/2",
            source_key="bbc_tech",
            title="AI Chip Breakthrough",
            summary="New chip doubles performance.",
            published_at=datetime(2026, 6, 7, 7, 0, tzinfo=timezone.utc),
            tags=["global", "tech"],
        ),
    ]
    news_store = MagicMock()
    news_store.get_personalized = AsyncMock(return_value=(articles, []))

    b, _ = make_briefing(notifier=notifier, news_store=news_store)
    await b.run()

    text = notifier.notify.call_args[0][2]
    assert "Headlines" in text
    assert "Global Summit Concludes" in text
    assert "AI Chip Breakthrough" in text
    assert "bbc_world" in text
    news_store.get_personalized.assert_awaited_once()


async def test_briefing_omits_headlines_when_news_store_absent():
    notifier = make_notifier()
    b, _ = make_briefing(notifier=notifier, news_store=None)
    await b.run()

    text = notifier.notify.call_args[0][2]
    assert "Headlines" not in text


async def test_briefing_omits_headlines_when_store_returns_empty():
    notifier = make_notifier()
    news_store = MagicMock()
    news_store.get_personalized = AsyncMock(return_value=([], []))

    b, _ = make_briefing(notifier=notifier, news_store=news_store)
    await b.run()

    text = notifier.notify.call_args[0][2]
    assert "Headlines" not in text


def make_briefing_with_personalization(
    *,
    notifier=None,
    news_store=None,
    memory_store=None,
    goal_store=None,
    dedup=False,
):
    notifier = notifier or make_notifier()
    notifier.on_cooldown = AsyncMock(return_value=dedup)

    memory = memory_store or MagicMock()
    if not isinstance(memory, MagicMock) or not hasattr(
        memory.count_unreviewed_facts, "_mock_name"
    ):
        memory = MagicMock()
    memory.count_unreviewed_facts = AsyncMock(return_value=0)

    workflow_store = MagicMock()
    workflow_store.list_enabled_scheduled = AsyncMock(return_value=[])
    workflow_store.list_failed_executions = AsyncMock(return_value=[])

    b = MorningBriefing(
        notifier=notifier,
        memory_store=memory_store or memory,
        workflow_store=workflow_store,
        settings=make_settings(),
        news_store=news_store,
        goal_store=goal_store,
        priority_view=make_priority_view(),
    )
    return b


async def test_briefing_personalized_shows_relevant_and_discovery():
    notifier = make_notifier()

    relevant_articles = [
        Article(
            url="https://bbc.com/1",
            source_key="bbc_tech",
            title="AI Chip Breakthrough",
            summary="New chip doubles performance.",
            published_at=datetime(2026, 6, 7, 8, 0, tzinfo=timezone.utc),
            tags=["global", "tech"],
        )
    ]
    discovery_articles = [
        Article(
            url="https://bbc.com/2",
            source_key="bbc_world",
            title="Global Summit Concludes",
            summary="Leaders reached an agreement.",
            published_at=datetime(2026, 6, 7, 7, 0, tzinfo=timezone.utc),
            tags=["global"],
        )
    ]

    news_store = MagicMock()
    news_store.get_personalized = AsyncMock(
        return_value=(relevant_articles, discovery_articles)
    )

    memory_store = MagicMock()
    memory_store.count_unreviewed_facts = AsyncMock(return_value=0)
    memory_store.list_recent_facts = AsyncMock(return_value=[])
    memory_store.get_profile = AsyncMock(return_value=[])

    b = make_briefing_with_personalization(
        notifier=notifier,
        news_store=news_store,
        memory_store=memory_store,
    )
    await b.run()

    text = notifier.notify.call_args[0][2]
    assert "AI Chip Breakthrough" in text
    assert "Outside your usual" in text
    assert "Global Summit Concludes" in text


async def test_briefing_personalized_shows_only_relevant_when_no_discovery():
    notifier = make_notifier()

    relevant_articles = [
        Article(
            url="https://bbc.com/1",
            source_key="bbc_tech",
            title="AI Chip Breakthrough",
            summary="New chip doubles performance.",
            published_at=datetime(2026, 6, 7, 8, 0, tzinfo=timezone.utc),
            tags=["global", "tech"],
        )
    ]

    news_store = MagicMock()
    news_store.get_personalized = AsyncMock(return_value=(relevant_articles, []))

    memory_store = MagicMock()
    memory_store.count_unreviewed_facts = AsyncMock(return_value=0)
    memory_store.list_recent_facts = AsyncMock(return_value=[])
    memory_store.get_profile = AsyncMock(return_value=[])

    b = make_briefing_with_personalization(
        notifier=notifier,
        news_store=news_store,
        memory_store=memory_store,
    )
    await b.run()

    text = notifier.notify.call_args[0][2]
    assert "AI Chip Breakthrough" in text
    assert "Outside your usual" not in text


async def test_briefing_personalized_header_when_sufficient_facts():
    notifier = make_notifier()
    relevant_articles = [
        Article(
            url="https://bbc.com/1",
            source_key="bbc_tech",
            title="AI News",
            summary="AI advances.",
            published_at=datetime(2026, 6, 7, 8, 0, tzinfo=timezone.utc),
            tags=["global"],
        )
    ]
    news_store = MagicMock()
    news_store.get_personalized = AsyncMock(return_value=(relevant_articles, []))

    facts = [
        SimpleNamespace(
            predicate="news_interest",
            value=f"topic_{i}",
            confidence=0.9,
            contradicted=False,
        )
        for i in range(6)
    ]
    memory_store = MagicMock()
    memory_store.count_unreviewed_facts = AsyncMock(return_value=0)
    memory_store.list_recent_facts = AsyncMock(return_value=facts)
    memory_store.get_profile = AsyncMock(return_value=[])

    b = make_briefing_with_personalization(
        notifier=notifier,
        news_store=news_store,
        memory_store=memory_store,
    )
    await b.run()

    text = notifier.notify.call_args[0][2]
    assert "For you (based on your interests)" in text


async def test_briefing_ignores_activity_facts_for_personalization():
    notifier = make_notifier()
    news_store = MagicMock()
    news_store.get_personalized = AsyncMock(return_value=([], []))

    memory_store = MagicMock()
    memory_store.count_unreviewed_facts = AsyncMock(return_value=0)
    memory_store.list_recent_facts = AsyncMock(
        return_value=[
            SimpleNamespace(
                predicate="activity_programming",
                value="programming the AI assistant",
                confidence=0.9,
                contradicted=False,
            ),
        ]
    )
    memory_store.get_profile = AsyncMock(return_value=[])

    b = make_briefing_with_personalization(
        notifier=notifier,
        news_store=news_store,
        memory_store=memory_store,
    )
    await b.run()

    ctx = news_store.get_personalized.await_args.kwargs["ctx"]
    assert "programming" not in ctx.interest_text


async def test_briefing_personalized_fallback_on_get_personalized_error():
    notifier = make_notifier()
    articles = [
        Article(
            url="https://bbc.com/1",
            source_key="bbc_world",
            title="Fallback Headline",
            summary="Fallback.",
            published_at=datetime(2026, 6, 7, 8, 0, tzinfo=timezone.utc),
            tags=["global"],
        )
    ]
    news_store = MagicMock()
    news_store.get_personalized = AsyncMock(side_effect=Exception("db error"))
    news_store.get_recent = AsyncMock(return_value=articles)

    memory_store = MagicMock()
    memory_store.count_unreviewed_facts = AsyncMock(return_value=0)
    memory_store.list_recent_facts = AsyncMock(return_value=[])
    memory_store.get_profile = AsyncMock(return_value=[])

    b = make_briefing_with_personalization(
        notifier=notifier,
        news_store=news_store,
        memory_store=memory_store,
    )
    await b.run()

    text = notifier.notify.call_args[0][2]
    assert "Fallback Headline" in text
    news_store.get_recent.assert_awaited_once()
