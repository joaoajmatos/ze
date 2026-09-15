from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from ze_agents.claims import Provenance
from ze_onboarding.persistence import OnboardingPersistence
from ze_onboarding.types import StoredOnboardingSeed
from ze_plugin.contribution import TargetFace


def _seed(*, kind: str, key: str = "preferred_name", value: str = "Joao") -> StoredOnboardingSeed:
    return StoredOnboardingSeed(
        id=uuid4(),
        session_id=uuid4(),
        step_id=uuid4(),
        plugin=None,
        kind=kind,
        key=key,
        value=value,
        confidence=0.95,
        review_status="approved",
    )


async def test_apply_memory_fact_is_prompt_supplied_and_reviewed() -> None:
    store = AsyncMock()
    persistence = OnboardingPersistence(memory_store=store)
    with patch(
        "ze_onboarding.persistence.submit_perception_facts",
        new_callable=AsyncMock,
    ) as submit:
        await persistence.apply([_seed(kind="memory_fact")])
    store.propose_facts.assert_not_called()
    submit.assert_awaited_once()
    item = submit.await_args.args[1][0]
    assert item.provenance == Provenance.PROMPT_SUPPLIED
    assert item.target_face == TargetFace.USER
    assert item.fact.reviewed is True
    assert item.fact.predicate == "preferred_name"
    assert item.fact.value == "Joao"


async def test_apply_profile_facet_unchanged() -> None:
    store = AsyncMock()
    persistence = OnboardingPersistence(memory_store=store)
    with patch(
        "ze_onboarding.persistence.submit_perception_facts",
        new_callable=AsyncMock,
    ) as submit:
        await persistence.apply([_seed(kind="profile_facet", key="locale", value="pt")])
    submit.assert_not_awaited()
    store.upsert_profile_facets.assert_awaited_once()


async def test_apply_plugin_setting_unchanged() -> None:
    setter = AsyncMock()
    store = AsyncMock()
    persistence = OnboardingPersistence(
        memory_store=store,
        plugin_setting_setters={"calendar": setter},
    )
    seed = StoredOnboardingSeed(
        id=uuid4(),
        session_id=uuid4(),
        step_id=uuid4(),
        plugin="calendar",
        kind="plugin_setting",
        key="timezone",
        value="Europe/Lisbon",
        confidence=1.0,
        review_status="approved",
    )
    with patch(
        "ze_onboarding.persistence.submit_perception_facts",
        new_callable=AsyncMock,
    ) as submit:
        await persistence.apply([seed])
    submit.assert_not_awaited()
    setter.assert_awaited_once_with("timezone", "Europe/Lisbon")
