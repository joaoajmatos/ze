"""READ tools companion calls to put a composed answer on screen. The components are
appended to the turn; the model gets only the summary to write its sentence from."""

from __future__ import annotations

from ze_agents.tool import Injected, ToolAccess, tool
from ze_components import context as component_context

from ze_priority.compose.composer import WorldComposer
from ze_priority.compose.types import Composition

SLIPPING_KEY = "slipping"
DECISIONS_KEY = "decisions"


def topic_key(topic: str) -> str:
    return "topic:" + " ".join(topic.lower().split())


def _deliver(composition: Composition, *, own_key: str, preset: str | None) -> dict:
    # A preset turn already shows these components at its head.
    if preset != own_key:
        for component in composition.components:
            component_context.append_serialized(component)
    return {
        "summary": composition.summary,
        "sources_failed": composition.sources_failed,
    }


@tool(
    access=ToolAccess.READ,
    description=(
        "Show what is slipping: drifting loops, stuck goals, what is due in the next "
        "7 days. The modules appear on screen; you get a summary to write one or two "
        "sentences from."
    ),
)
async def show_slipping(
    world_composer: WorldComposer,
    preset: Injected[str | None] = None,
) -> dict:
    composition = await world_composer.compose_slipping()
    return _deliver(composition, own_key=SLIPPING_KEY, preset=preset)


@tool(
    access=ToolAccess.READ,
    description=(
        "Show what needs the user to decide: held writes, goals waiting at a gate, "
        "suspected loops. The modules appear on screen; you get a summary to write "
        "one or two sentences from."
    ),
)
async def show_decisions(
    world_composer: WorldComposer,
    preset: Injected[str | None] = None,
) -> dict:
    composition = await world_composer.compose_decisions()
    return _deliver(composition, own_key=DECISIONS_KEY, preset=preset)


@tool(
    access=ToolAccess.READ,
    description=(
        "Show how one project or topic is going: its open loops, goals, workflows and "
        "hypotheses. topic is the user's own words for it. The modules appear on "
        "screen; you get a summary to write one or two sentences from."
    ),
)
async def show_topic(
    world_composer: WorldComposer,
    topic: str,
    preset: Injected[str | None] = None,
) -> dict:
    composition = await world_composer.compose_topic(topic)
    return _deliver(composition, own_key=topic_key(topic), preset=preset)
