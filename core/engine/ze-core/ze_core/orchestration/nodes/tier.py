"""choose_tier — after match_skills, decide whether the agent runs its light model."""

from __future__ import annotations

from dataclasses import replace

from langchain_core.runnables import RunnableConfig
from ze_agents.judgment import gate
from ze_logging import get_logger

from ze_core.conversation.messages.judgments import judgment_rows
from ze_core.conversation.messages.types import TierTrace
from ze_core.orchestration.judgment_state import build_tier_state
from ze_core.orchestration.state import AgentState
from ze_core.routing.tier import TierJudge, resolve_agent_model
from ze_core.telemetry.context import get_cost_context, set_agent_context

log = get_logger(__name__)


def _not_asked(envelope, decided_by: str) -> dict:
    subtask = envelope.subtasks[0]
    return {"tier": TierTrace(subtask.agent, "full", decided_by, subtask.model)}


async def choose_tier(state: AgentState, config: RunnableConfig) -> dict:
    """Routing assigned every subtask its full model; swap in ``model_simple`` only for a
    single-agent turn that System One judges light. Every other path keeps the full model."""
    envelope = state.get("envelope")
    if envelope is None or not envelope.subtasks:
        return {}

    if (
        len(envelope.subtasks) != 1
        or envelope.is_compound
        or state.get("conductor_hint")
    ):
        return _not_asked(envelope, "compound")

    judge: TierJudge | None = config["configurable"].get("tier_judge")
    if judge is None:
        return _not_asked(envelope, "off")

    subtask = envelope.subtasks[0]
    if resolve_agent_model(subtask.agent, "simple", judge.app_config) == (
        resolve_agent_model(subtask.agent, "full", judge.app_config)
    ):
        return _not_asked(envelope, "no_simple_model")
    not_asked = gate(judge.surface, judge.client)
    if not_asked == "disabled":
        return _not_asked(envelope, "off")
    if not_asked == "uncalibrated":
        return _not_asked(envelope, "uncalibrated")
    if not_asked == "unavailable":
        return _not_asked(envelope, "off")

    previous_agent = get_cost_context().agent
    set_agent_context("router")
    try:
        outcome = await judge.choose(envelope, build_tier_state(state))
    except Exception as exc:
        log.warning("tier_node_error", agent=subtask.agent, error=str(exc))
        return _not_asked(envelope, "skip")
    finally:
        set_agent_context(previous_agent)

    update: dict = {}
    model = subtask.model
    if outcome.decision.tier == "simple":
        model = outcome.model
        update["envelope"] = replace(
            envelope, subtasks=[replace(subtask, model=outcome.model)]
        )
    update["tier"] = TierTrace(
        subtask.agent, outcome.decision.tier, outcome.decision.decided_by, model
    )
    if outcome.judgment is not None:
        rows = judgment_rows(outcome.judgment)
        update["judgments"] = [*(state.get("judgments") or []), *rows]
    return update
