from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from ze_agents.client import LLMClient
from ze_logging import get_logger
from ze_memory.graph.store import GraphStore
from ze_collision.detect import submit_and_detect_collisions
from ze_plugin.contribution import EvidenceRef

from ze_worldstate import drift
from ze_worldstate.corroboration import corroborate_match
from ze_worldstate.contribution import loop_to_contribution
from ze_worldstate.fingerprint import compute_evidence_fingerprint
from ze_worldstate.matching import find_matching_loop
from ze_worldstate.loop_judge import capped_text, supported_provenance
from ze_worldstate.store import LoopStore
from ze_worldstate.types import (
    DECLARED_CONFIDENCE,
    LoopAdmission,
    LoopProvenance,
    LoopSource,
    LoopSourceRole,
    LoopState,
    OpenLoop,
    SourceKey,
    TitleWriterResult,
)

log = get_logger(__name__)

DEFAULT_EXTRACTION_MODEL = "anthropic/claude-haiku-4-5"

_SUSPECTED_CONFIDENCE = 0.3

_SYSTEM_PROMPT = """You are the relevance gate for Ze's open-loop substrate. Given a
short piece of text, decide whether it implies a genuine unfinished commitment,
task, or concern the user (or someone in their life) still needs to act on —
an "open loop" (e.g. "I need to renew my passport", "I told Maria I'd send the
contract") — OR whether it reports that a previously-open commitment is now done
(e.g. "I followed up with the accountant, it's done").

Be conservative: ordinary conversational content ("what's the weather",
"thanks!", small talk, questions) is neither.

Also decide whether the user is *explicitly declaring* the commitment themselves
("remind me I need to...", "I need to...", "I have to...") as opposed to it being
merely implied/inferred from context.

Also decide, only when `is_loop` is true, whether the text implies a specific
timeframe by which the commitment should be resolved (e.g. "by Friday", "next
week") — if so, express it as a whole number of days from now; otherwise omit it.

Respond with a JSON object only:
{
  "is_loop": true|false,
  "title": "short human-readable title, or empty string",
  "explicit_declaration": true|false,
  "resolves_existing": true|false,
  "implied_window_days": <integer, optional>
}
`resolves_existing` is true only when the text reports an existing commitment as
done/finished — in that case `is_loop` should be false and `title` is the short
description of the commitment that was resolved.
"""


class _ExtractionGateResult:
    __slots__ = (
        "is_loop",
        "title",
        "explicit_declaration",
        "resolves_existing",
        "implied_window_days",
    )

    def __init__(
        self,
        is_loop: bool,
        title: str,
        explicit_declaration: bool,
        resolves_existing: bool,
        implied_window_days: int | None = None,
    ) -> None:
        self.is_loop = is_loop
        self.title = title
        self.explicit_declaration = explicit_declaration
        self.resolves_existing = resolves_existing
        self.implied_window_days = implied_window_days


async def _run_extraction_gate(
    text: str, llm_client: LLMClient, model: str
) -> _ExtractionGateResult | None:
    try:
        raw = await llm_client.complete(
            [{"role": "user", "content": text}],
            model=model,
            system=_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        parsed = _loads_json(raw)
    except Exception as exc:
        log.warning("loop_extraction_gate_failed", error=str(exc))
        return None

    raw_window = parsed.get("implied_window_days")
    implied_window_days = (
        int(raw_window) if isinstance(raw_window, (int, float)) else None
    )

    return _ExtractionGateResult(
        is_loop=bool(parsed.get("is_loop")),
        title=str(parsed.get("title") or "").strip(),
        explicit_declaration=bool(parsed.get("explicit_declaration")),
        resolves_existing=bool(parsed.get("resolves_existing")),
        implied_window_days=implied_window_days,
    )


_WRITER_PROMPT = """You write the short title of one open loop for Ze. The text has already
been judged: it {what}. Reply with a JSON object only:
{{"title": "short human-readable title"{window_field}}}
The title names the commitment itself, in the language of the text, in under ten words.{window_rule}
"""

_WRITER_CREATE = ("implies an unfinished commitment the user still has to act on", True)
_WRITER_RESOLVE = ("reports that a commitment the user had is now done", False)


def _loads_json(raw: str) -> Any:
    """Haiku wraps JSON replies in a ```json fence even with response_format set."""
    text = raw.strip()
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in reply")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj


def _whole_days(raw: Any) -> int | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    if isinstance(raw, float) and raw.is_integer() and raw > 0:
        return int(raw)
    return None


async def write_loop_title(
    text: str, kind: str, llm_client: LLMClient, model: str
) -> TitleWriterResult | None:
    """Haiku writes the title (and, for creates, an implied window). It never decides existence."""
    what, with_window = _WRITER_CREATE if kind == "create" else _WRITER_RESOLVE
    system = _WRITER_PROMPT.format(
        what=what,
        window_field=', "implied_window_days": <integer, optional>'
        if with_window
        else "",
        window_rule=(
            " Include `implied_window_days` only if the text names a timeframe, as a whole"
            " number of days from now; otherwise omit it."
            if with_window
            else ""
        ),
    )
    try:
        raw = await llm_client.complete(
            [{"role": "user", "content": text}],
            model=model,
            system=system,
            temperature=0.0,
            max_tokens=120,
            response_format={"type": "json_object"},
        )
        parsed = _loads_json(raw)
        title = str(parsed.get("title") or "").strip()
    except Exception as exc:
        log.warning("loop_title_writer_failed", error=str(exc))
        return None
    if not title:
        log.warning("loop_title_writer_empty")
        return None
    window = _whole_days(parsed.get("implied_window_days")) if with_window else None
    return TitleWriterResult(title=title, implied_window_days=window)


async def resolve_entities(entity_resolver: Any, text: str) -> list[UUID]:
    if entity_resolver is None:
        return []
    try:
        return list(await entity_resolver(text))
    except Exception as exc:
        log.warning("loop_entity_resolution_failed", error=str(exc))
        return []


async def _link_evidence_and_entities(
    loop_id: UUID,
    evidence_refs: list[EvidenceRef],
    entity_ids: list[UUID],
    loop_store: LoopStore,
) -> None:
    for ref in evidence_refs:
        await loop_store.link_evidence(loop_id, ref.kind, ref.id)
    for entity_id in entity_ids:
        await loop_store.link_entity(loop_id, entity_id)


def _existence_checkers(memory_store: Any):
    async def _check_fact_exists(fact_id: UUID) -> bool:
        if memory_store is None:
            return False
        facts = await memory_store.get_facts_by_ids([fact_id])
        return len(facts) > 0

    async def _check_episode_exists(episode_id: UUID) -> bool:
        if memory_store is None:
            return False
        episodes = await memory_store.get_episodes_by_ids([episode_id])
        return len(episodes) > 0

    return _check_fact_exists, _check_episode_exists


async def _corroborate_match(
    existing: OpenLoop,
    evidence_refs: list[EvidenceRef],
    entity_ids: list[UUID],
    loop_store: LoopStore,
) -> None:
    await _link_evidence_and_entities(existing.id, evidence_refs, entity_ids, loop_store)
    if evidence_refs and existing.state is LoopState.ACTIVE:
        await loop_store.record_corroboration(existing.id)


async def _record_origin(
    loop_id: UUID,
    source: SourceKey | None,
    evidence_refs: list[EvidenceRef],
    loop_store: LoopStore,
) -> None:
    if source is None or not source.ref:
        return
    try:
        await loop_store.add_source(
            LoopSource(
                loop_id=loop_id,
                role=LoopSourceRole.ORIGIN,
                key=source,
                evidence=evidence_refs[0] if evidence_refs else None,
            )
        )
    except Exception as exc:
        log.warning("loop_origin_source_failed", loop_id=str(loop_id), error=str(exc))


async def _match_existing(
    existing: OpenLoop,
    dropped: OpenLoop | None,
    *,
    text: str,
    prov: str,
    source: SourceKey | None,
    evidence_refs: list[EvidenceRef],
    entity_ids: list[UUID],
    loop_store: LoopStore,
    system_one_client: Any,
    settings: Any,
) -> None:
    async def link() -> None:
        await _corroborate_match(existing, evidence_refs, entity_ids, loop_store)

    if existing.state is not LoopState.SUSPECTED:
        await link()
        return
    await corroborate_match(
        existing=existing,
        text=text,
        inflow=source.inflow if source else prov,
        key=source,
        evidence_refs=evidence_refs,
        entity_ids=entity_ids,
        dropped=dropped,
        loop_store=loop_store,
        system_one_client=system_one_client,
        settings=settings,
        link=link,
    )


async def _create_declared_loop(
    title: str,
    prov: str,
    evidence_refs: list[EvidenceRef],
    entity_ids: list[UUID],
    loop_store: LoopStore,
    graph_store: GraphStore | None,
    embedder: Any,
    memory_store: Any,
    implied_window_days: int | None = None,
    collision_store: Any = None,
    nli_client: Any = None,
    text: str = "",
    source: SourceKey | None = None,
    system_one_client: Any = None,
    settings: Any = None,
) -> OpenLoop:
    if graph_store is not None:
        existing = await find_matching_loop(
            entity_ids,
            title,
            loop_store=loop_store,
            graph_store=graph_store,
            embedder=embedder,
            states=["suspected", "active", "drifting"],
        )
        if existing is not None:
            dropped = None
            if existing.state is LoopState.SUSPECTED:
                dropped = await find_matching_loop(
                    entity_ids,
                    title,
                    loop_store=loop_store,
                    graph_store=graph_store,
                    embedder=embedder,
                    states=["dropped"],
                )
            await _match_existing(
                existing,
                dropped,
                text=text or title,
                prov=prov,
                source=source,
                evidence_refs=evidence_refs,
                entity_ids=entity_ids,
                loop_store=loop_store,
                system_one_client=system_one_client,
                settings=settings,
            )
            return existing

    check_fact_exists, check_episode_exists = _existence_checkers(memory_store)
    confirmed_at = datetime.now(timezone.utc)
    loop = OpenLoop(
        title=title,
        provenance=LoopProvenance.USER_DECLARED
        if prov == LoopProvenance.CONVERSATION
        else prov,
        confidence=DECLARED_CONFIDENCE,
        state=LoopState.ACTIVE,
        confirmed_at=confirmed_at,
        drift_deadline=drift.compute_drift_deadline(confirmed_at, implied_window_days),
    )
    created = await submit_and_detect_collisions(
        loop_to_contribution(loop, entity_ids=entity_ids),
        lambda: loop_store.create(loop),
        result_id=lambda c: c.id,
        producer_kind="open_loop",
        check_fact_exists=check_fact_exists,
        check_episode_exists=check_episode_exists,
        collision_store=collision_store,
        nli_client=nli_client,
    )
    await loop_store.set_drift_deadline(created.id, loop.drift_deadline)
    created.drift_deadline = loop.drift_deadline
    await _link_evidence_and_entities(created.id, evidence_refs, entity_ids, loop_store)
    await _record_origin(created.id, source, evidence_refs, loop_store)
    return created


async def _close_matching_loop(
    title: str,
    entity_ids: list[UUID],
    loop_store: LoopStore,
    graph_store: GraphStore | None,
    embedder: Any,
    evidence_refs: list[EvidenceRef],
) -> list[OpenLoop]:
    if graph_store is None:
        return []
    existing = await find_matching_loop(
        entity_ids,
        title,
        loop_store=loop_store,
        graph_store=graph_store,
        embedder=embedder,
        states=["suspected", "active", "drifting"],
    )
    if existing is None:
        return []
    closed = await loop_store.resolve(existing.id, evidence_refs)
    return [closed] if closed is not None else []


async def _create_suspected_loop(
    title: str,
    prov: str,
    evidence_refs: list[EvidenceRef],
    entity_ids: list[UUID],
    loop_store: LoopStore,
    graph_store: GraphStore | None,
    embedder: Any,
    memory_store: Any,
    collision_store: Any,
    nli_client: Any,
    text: str = "",
    source: SourceKey | None = None,
    system_one_client: Any = None,
    settings: Any = None,
) -> list[OpenLoop]:
    fingerprint = compute_evidence_fingerprint(evidence_refs)

    if graph_store is not None:
        dismissed = await find_matching_loop(
            entity_ids,
            title,
            loop_store=loop_store,
            graph_store=graph_store,
            embedder=embedder,
            states=["dropped"],
        )
        if (
            dismissed is not None
            and dismissed.dismissed_evidence_fingerprint == fingerprint
        ):
            # FR-011: don't resurface a loop from evidence the user already dismissed.
            return []

        existing = await find_matching_loop(
            entity_ids,
            title,
            loop_store=loop_store,
            graph_store=graph_store,
            embedder=embedder,
            states=["suspected", "active", "drifting"],
        )
        if existing is not None:
            await _match_existing(
                existing,
                dismissed,
                text=text or title,
                prov=prov,
                source=source,
                evidence_refs=evidence_refs,
                entity_ids=entity_ids,
                loop_store=loop_store,
                system_one_client=system_one_client,
                settings=settings,
            )
            return [existing]

    loop = OpenLoop(
        title=title,
        provenance=prov,
        confidence=_SUSPECTED_CONFIDENCE,
        state=LoopState.SUSPECTED,
    )

    check_fact_exists, check_episode_exists = _existence_checkers(memory_store)

    created = await submit_and_detect_collisions(
        loop_to_contribution(loop, evidence=evidence_refs, entity_ids=entity_ids),
        lambda: loop_store.create(loop),
        result_id=lambda c: c.id,
        producer_kind="open_loop",
        check_fact_exists=check_fact_exists,
        check_episode_exists=check_episode_exists,
        collision_store=collision_store,
        nli_client=nli_client,
    )
    await _link_evidence_and_entities(created.id, evidence_refs, entity_ids, loop_store)
    await _record_origin(created.id, source, evidence_refs, loop_store)
    return [created]


async def _commit_admitted(
    text: str,
    prov: str,
    admission: LoopAdmission,
    evidence_refs: list[EvidenceRef],
    entity_ids: list[UUID],
    llm_client: LLMClient,
    embedder: Any,
    loop_store: LoopStore,
    graph_store: GraphStore | None,
    memory_store: Any,
    model: str,
    collision_store: Any,
    nli_client: Any,
    source: SourceKey | None = None,
    system_one_client: Any = None,
    settings: Any = None,
) -> list[OpenLoop]:
    """System One already decided; Haiku only writes the title (and a create window)."""
    kind = admission.decision.kind
    writer_text = capped_text(text, prov) if supported_provenance(prov) else text
    written = await write_loop_title(
        writer_text, "resolve" if kind == "resolve" else "create", llm_client, model
    )
    if written is None:
        return []
    if kind == "resolve":
        return await _close_matching_loop(
            written.title, entity_ids, loop_store, graph_store, embedder, evidence_refs
        )
    if kind == "create_declared":
        created = await _create_declared_loop(
            written.title,
            prov,
            evidence_refs,
            entity_ids,
            loop_store,
            graph_store,
            embedder,
            memory_store,
            implied_window_days=written.implied_window_days,
            collision_store=collision_store,
            nli_client=nli_client,
            text=text,
            source=source,
            system_one_client=system_one_client,
            settings=settings,
        )
        return [created]
    return await _create_suspected_loop(
        written.title,
        prov,
        evidence_refs,
        entity_ids,
        loop_store,
        graph_store,
        embedder,
        memory_store,
        collision_store,
        nli_client,
        text=text,
        source=source,
        system_one_client=system_one_client,
        settings=settings,
    )


async def propose_loop_candidates(
    text: str,
    provenance: str,
    evidence_refs: list[EvidenceRef],
    llm_client: LLMClient,
    embedder: Any,
    loop_store: LoopStore,
    entity_resolver: Any,
    *,
    graph_store: GraphStore | None = None,
    memory_store: Any = None,
    model: str = DEFAULT_EXTRACTION_MODEL,
    collision_store: Any = None,
    nli_client: Any = None,
    admission: LoopAdmission | None = None,
    source: SourceKey | None = None,
    system_one_client: Any = None,
    settings: Any = None,
) -> list[OpenLoop]:
    """Conservative, relevance-gated (FR-009). Returns [] for ordinary content.

    `provenance` is honoured as-is (never model narration, FR-003). Non-
    `user_declared` inflows are conservative/relevance-gated and always land
    in `suspected` at low confidence (FR-005), UNLESS the single relevance-gate
    call also classifies the text as an explicit self-declaration (FR-006) — in
    which case the loop is created directly in `active` at high confidence with
    provenance `user_declared`, bypassing matching entirely, without requiring a
    separate call-site classification step. Passing `provenance="user_declared"`
    directly (e.g. from a future non-conversational declared-loop caller) always
    takes this path too.

    `admission` (phase 168): a System One decision made by `LoopInflow`. When it
    resolves, declares or suspects, Haiku only writes the title and the 109 gate does
    not run. `None`, a `fallback` or a `hold` admission leaves the 109 Haiku gate as is.
    """
    prov = provenance
    entity_ids = await resolve_entities(entity_resolver, text)

    if prov == LoopProvenance.USER_DECLARED:
        created = await _create_declared_loop(
            text.strip(),
            prov,
            evidence_refs,
            entity_ids,
            loop_store,
            graph_store,
            embedder,
            memory_store,
            collision_store=collision_store,
            nli_client=nli_client,
            text=text,
            source=source,
            system_one_client=system_one_client,
            settings=settings,
        )
        return [created]

    if admission is not None and admission.decision.kind in (
        "resolve",
        "create_declared",
        "create_suspected",
    ):
        return await _commit_admitted(
            text,
            prov,
            admission,
            evidence_refs,
            entity_ids,
            llm_client,
            embedder,
            loop_store,
            graph_store,
            memory_store,
            model,
            collision_store,
            nli_client,
            source=source,
            system_one_client=system_one_client,
            settings=settings,
        )

    gate = await _run_extraction_gate(text, llm_client, model)
    if gate is None:
        return []

    if gate.resolves_existing and gate.title and graph_store is not None:
        # T030: "it's done" recognition — resolve the matching loop instead of
        # creating a new one.
        return await _close_matching_loop(
            gate.title, entity_ids, loop_store, graph_store, embedder, evidence_refs
        )

    if not gate.is_loop or not gate.title:
        return []

    if gate.explicit_declaration:
        created = await _create_declared_loop(
            gate.title,
            prov,
            evidence_refs,
            entity_ids,
            loop_store,
            graph_store,
            embedder,
            memory_store,
            implied_window_days=gate.implied_window_days,
            collision_store=collision_store,
            nli_client=nli_client,
            text=text,
            source=source,
            system_one_client=system_one_client,
            settings=settings,
        )
        return [created]

    return await _create_suspected_loop(
        gate.title,
        prov,
        evidence_refs,
        entity_ids,
        loop_store,
        graph_store,
        embedder,
        memory_store,
        collision_store,
        nli_client,
        text=text,
        source=source,
        system_one_client=system_one_client,
        settings=settings,
    )
