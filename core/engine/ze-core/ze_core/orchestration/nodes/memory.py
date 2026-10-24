from __future__ import annotations

import asyncio
import dataclasses
from typing import Any

from langchain_core.runnables import RunnableConfig

from ze_agents.claims import Provenance
from ze_components.summary import describe_components
from ze_logging import get_logger
from ze_agents.defaults import MODEL_SYNTHESIS
from ze_agents.model_resolution import resolve_model
from ze_agents.tasks import fire_and_forget
from ze_core.conversation.messages.judgments import judgments_from_result
from ze_core.conversation.messages.types import JudgmentTrace
from ze_core.orchestration.judgment_bars import intake_bars
from ze_core.openrouter.context_windows import get_context_window
from ze_core.orchestration.nodes.context import SESSION_HISTORY_LIMIT
from ze_core.orchestration.nodes.correlation import _format_text_section
from ze_core.orchestration.state import AgentState
from ze_core.telemetry.context import set_agent_context
from ze_agents.types import AgentResult
from ze_memory.contribution import PerceptionFactSubmit, submit_perception_facts
from ze_memory.fact_judge import FACT_QUESTIONS
from ze_memory.fact_identity import fact_identity, identities_from_remember_calls
from ze_plugin.contribution import EvidenceRef, TargetFace

log = get_logger(__name__)

_COMPACTION_TOKEN_BUDGET_FRACTION = 0.7

_COMPACTION_SYSTEM = (
    "You are compacting an in-progress conversation for a personal AI assistant. "
    "Condense the older portion of the conversation below into compact reference "
    "notes the assistant can act on — not a narrative topic recap. Preserve: "
    "decisions made, constraints or preferences stated, outstanding tasks or open "
    "questions, and outcomes of prior actions. Do not add information not present "
    "in the source. Be concise."
)


def _estimate_tokens(messages: list[dict]) -> int:
    chars = sum(len(str(m.get("content", ""))) for m in messages)
    return chars // 4


def _format_transcript(messages: list[dict]) -> str:
    return "\n".join(
        f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages
    )


async def _run_fact_extractor(
    fact_extractor: Any, config: RunnableConfig, result: AgentResult, ctx: Any
) -> Any:
    if fact_extractor is None:
        return None
    return await fact_extractor(
        config["configurable"],
        agent=result.agent,
        prompt=ctx.prompt,
        response=result.response,
    )


async def _run_commitment_intake(
    commitment_intake: Any, config: RunnableConfig, result: AgentResult, ctx: Any
) -> Any:
    """Phase 173 intake; it falls back internally, so a failure here only drops the turn's judgment."""
    try:
        return await commitment_intake(
            config["configurable"],
            prompt=ctx.prompt,
            response=result.response,
            agent=result.agent,
            tool_calls=result.tool_calls or [],
        )
    except Exception as exc:
        log.warning("write_memory_commitment_intake_failed", error=str(exc))
        return None


def _outcome_row(intake: Any) -> JudgmentTrace | None:
    """The merged decision as one trace row, so link and waiting_on are visible (FR-018)."""
    outcome = getattr(intake, "outcome", None)
    judgment = intake.judgment
    if outcome is None or judgment is None:
        return None
    answer = f"{outcome.kind}:{outcome.reason}"
    if outcome.link_kind:
        answer += f":{outcome.link_kind}"
    return JudgmentTrace(
        question_id="intake_outcome",
        kind="choice",
        latency_ms=judgment.latency_ms,
        answer=answer,
        consumed=True,
        skip_reason=intake.skip_reason,
        surface="commitment_intake",
    )


async def write_memory(state: AgentState, config: RunnableConfig) -> dict:
    set_agent_context("memory_write")
    store: Any = config["configurable"]["memory_store"]
    embedder: Any = config["configurable"]["embedder"]
    ctx = state.get("agent_context")

    if ctx is None:
        return {}

    thread_id: str = config["configurable"].get("thread_id", "")
    is_eval = thread_id.startswith("eval-")
    # Phase 165: a retry only regenerates text. It writes no episode, fact, event,
    # entity, procedure or hook side effect; it still extends session history.
    is_retry = bool(config["configurable"].get("retry_mode"))

    result: AgentResult | None = state.get("agent_result")
    final_response = state.get("final_response")

    if result is None:
        envelope = state.get("envelope")
        agent_name = envelope.primary_agent if envelope else "unknown"
        if final_response:
            result = AgentResult(
                agent=agent_name,
                response=final_response,
            )
        else:
            error_msg = state.get("error") or "unknown error"
            result = AgentResult(agent=agent_name, response=f"[ERROR] {error_msg}")

    reply = final_response or result.response

    from ze_core.orchestration.procedure_activation import complete_procedure_invocation

    if not is_retry:
        await complete_procedure_invocation(ctx, result, config)

    proposals: list = []
    admission_path = "none"
    judged_trace: Any = None
    if not is_eval and not is_retry:
        embedding = embedder.encode_passage(ctx.prompt)
        episode_task = fire_and_forget(
            store.write_episode(
                session_id=ctx.session_id,
                agent=result.agent,
                prompt=ctx.prompt,
                response=reply,
                embedding=embedding,
            ),
            label="write_episode",
        )
        commitment_intake = config["configurable"].get("commitment_intake")
        trace = state.get("message_trace")
        rows: list = []
        loop_result = None
        if commitment_intake is not None:
            intake = await _run_commitment_intake(
                commitment_intake, config, result, ctx
            )
            fact_result = intake.fact if intake is not None else None
            loop_result = intake.loop if intake is not None else None
            if intake is not None and intake.judgment is not None:
                rows += judgments_from_result(
                    intake.judgment,
                    question_kinds=intake.question_kinds,
                    consumed=intake.consumed,
                    skip_reason=intake.skip_reason,
                    surface="commitment_intake",
                    bars=intake_bars(config["configurable"].get("settings")),
                )
                outcome_row = _outcome_row(intake)
                if outcome_row is not None:
                    rows.append(outcome_row)
        else:
            fact_result = await _run_fact_extractor(
                config["configurable"].get("fact_extractor"), config, result, ctx
            )
            if fact_result is not None and fact_result.judgment is not None:
                rows += judgments_from_result(
                    fact_result.judgment,
                    question_kinds={
                        qid: FACT_QUESTIONS[qid].type
                        for qid in fact_result.question_ids
                    },
                    consumed=fact_result.consumed,
                    skip_reason=fact_result.skip_reason,
                    surface="fact_judge",
                    bars={},
                )
        if fact_result is not None:
            proposals = fact_result.facts
            admission_path = fact_result.path
        if loop_result is not None and loop_result.commit is not None:
            fire_and_forget(
                _commit_with_episode(loop_result.commit, episode_task),
                label="loop_commit",
            )
        if rows and trace is not None:
            judged_trace = dataclasses.replace(
                trace, judgments=[*trace.judgments, *rows]
            )
        remembered = identities_from_remember_calls(result.tool_calls or [])
        if remembered:
            proposals = [
                fact
                for fact in proposals
                if fact_identity(fact.predicate, fact.value) not in remembered
            ]
        if proposals:
            items = [
                PerceptionFactSubmit(
                    fact=fact,
                    provenance=Provenance.PROMPT_SUPPLIED,
                    target_face=TargetFace.USER,
                    evidence=[],
                )
                for fact in proposals
            ]
            await submit_perception_facts(store, items)

        turn_extractor = config["configurable"].get("turn_extractor")
        if turn_extractor is not None:
            try:
                extracted = await turn_extractor(
                    config["configurable"],
                    prompt=ctx.prompt,
                    response=result.response,
                )
            except Exception as exc:
                log.warning("write_memory_turn_extractor_failed", error=str(exc))
                extracted = None
            if extracted is not None and extracted.events:
                fire_and_forget(
                    store.propose_events(extracted.events), label="propose_events"
                )
            for entity in extracted.entities if extracted is not None else []:
                fire_and_forget(
                    store.upsert_entity(entity),
                    label=f"upsert_entity:{entity.canonical_name}",
                )

        for hook in config["configurable"].get("memory_hooks", []):
            fire_and_forget(hook(result, ctx, config), label="memory_hook")

    log.debug(
        "orchestration_memory_write_scheduled",
        session_id=state["session_id"],
        extracted_facts=len(proposals) if not is_eval else 0,
        admission_path=admission_path,
        eval=is_eval,
    )
    trace_update: dict = {"message_trace": judged_trace} if judged_trace else {}

    if state.get("input_modality") == "image":
        user_content = f"[Image] {state.get('image_caption') or ''}"
    else:
        user_content = ctx.prompt

    # A components-only reply must not put empty content in history: providers
    # reject an empty non-final message on the next turn.
    history_reply = reply or (
        f"[{described}]"
        if (described := describe_components(state.get("components")))
        else reply
    )

    current = list(state.get("messages") or [])
    updated = current + [
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": history_reply},
    ]

    older_span = (
        updated[:-SESSION_HISTORY_LIMIT] if len(updated) > SESSION_HISTORY_LIMIT else []
    )
    if older_span and _should_compact(updated, ctx, config):
        tail = updated[-SESSION_HISTORY_LIMIT:]
        summary_message = await _compact(older_span, ctx, config)
        if summary_message is not None:
            return {"messages": [summary_message] + tail, **trace_update}

    trimmed = updated[-SESSION_HISTORY_LIMIT:]
    if older_span and updated[0].get("compaction_summary"):
        trimmed = [updated[0]] + trimmed
    return {"messages": trimmed, **trace_update}


async def _commit_with_episode(commit: Any, episode_task: asyncio.Task) -> Any:
    """Hand the loop commit the turn's episode as evidence once the write finishes."""
    episode_id = None
    try:
        episode_id = await episode_task
    except Exception:
        pass  # fire_and_forget already logged it
    refs = [EvidenceRef(kind="episode", id=episode_id)] if episode_id else []
    return await commit(refs)


def _should_compact(updated: list[dict], ctx: Any, config: RunnableConfig) -> bool:
    cfg: Any = config["configurable"].get("settings")
    app_config: dict = {}
    if cfg is not None:
        app_config = cfg if isinstance(cfg, dict) else getattr(cfg, "config", {})
    model = ctx.model or resolve_model("synthesis", MODEL_SYNTHESIS, app_config)
    context_window = get_context_window(model)
    return (
        _estimate_tokens(updated) >= context_window * _COMPACTION_TOKEN_BUDGET_FRACTION
    )


async def _compact(
    older_span: list[dict], ctx: Any, config: RunnableConfig
) -> dict | None:
    client: Any = config["configurable"].get("openrouter_client")
    cfg: Any = config["configurable"].get("settings")
    app_config: dict = {}
    if cfg is not None:
        app_config = cfg if isinstance(cfg, dict) else getattr(cfg, "config", {})
    model = ctx.model or resolve_model("synthesis", MODEL_SYNTHESIS, app_config)

    try:
        summary_text = await client.complete(
            messages=[
                {"role": "system", "content": _COMPACTION_SYSTEM},
                {"role": "user", "content": _format_transcript(older_span)},
            ],
            model=model,
        )
    except Exception as exc:
        log.warning("write_memory_compaction_failed", error=str(exc))
        return None

    return {
        "role": "system",
        "content": summary_text,
        "compaction_summary": True,
        "compaction_span": [0, len(older_span) - 1],
    }


async def synthesize(state: AgentState, config: RunnableConfig) -> dict:
    set_agent_context("synthesis")

    client: Any = config["configurable"]["openrouter_client"]
    cfg: Any = config["configurable"].get("settings")

    app_config: dict = {}
    if cfg is not None:
        app_config = cfg if isinstance(cfg, dict) else getattr(cfg, "config", {})
    synthesis_model = resolve_model("synthesis", MODEL_SYNTHESIS, app_config)

    subtask_results = state.get("subtask_results") or []
    if not subtask_results:
        return {}

    parts = "\n\n".join(f"[{r.agent}]: {r.response}" for r in subtask_results)
    synthesis_prompt = (
        "The following are responses from specialists that completed this compound request.\n"
        "Synthesize them into a single, coherent, well-structured response.\n"
        "Only these specialists finished. Do not claim that a missing, denied, or blocked job succeeded.\n\n"
        f"User request: {state['prompt']}\n\n"
        f"Agent responses:\n{parts}"
    )

    response = await client.complete(
        messages=[{"role": "user", "content": synthesis_prompt}],
        model=synthesis_model,
    )
    correlations = state.get("correlations") or []
    if correlations:
        response = response + "\n\n" + _format_text_section(correlations)

    log.info(
        "orchestration_synthesis_complete",
        session_id=state["session_id"],
        subtask_count=len(subtask_results),
    )
    return {"final_response": response}
