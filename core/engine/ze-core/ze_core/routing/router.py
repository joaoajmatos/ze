from __future__ import annotations

from typing import Any

from ze_agents.client import LLMClient
from ze_agents.judgment import Judgment, gate, judge
from ze_agents.errors import InvalidPromptError, RoutingError
from ze_logging import get_logger
from ze_agents.registry import get_enabled_agents
from ze_agents.tasks import fire_and_forget
from ze_core.routing.judge import (
    RoutingDecision,
    RoutingSurfaceConfig,
    build_questions,
    criterion_for,
    decide,
    read_decision,
    shortlist,
)
from ze_core.routing.store import RoutingStore
from ze_core.routing.tier import resolve_agent_model
from ze_core.routing.types import (
    RouterConfig,
    RoutingEnvelope,
    SubTask,
)

log = get_logger(__name__)


class EmbeddingRouter:
    def __init__(
        self,
        embedder: Any,
        openrouter_client: LLMClient,
        routing_store: RoutingStore | None = None,
        config: RouterConfig | None = None,
        app_config: dict | None = None,
        system_one_client: Any = None,
        surface: RoutingSurfaceConfig | None = None,
    ) -> None:
        self._embedder = embedder
        self._client = openrouter_client
        self._store = routing_store
        self._config = config or RouterConfig()
        self._app_config = app_config or {}
        self._system_one = system_one_client
        self._surface = surface or RoutingSurfaceConfig()

        self._agent_names: list[str] = []
        self._agent_matrix: Any = None
        self._load_agent_embeddings()

    @property
    def screen_hint(self) -> bool:
        return self._surface.screen_hint

    @property
    def config(self) -> RouterConfig:
        return self._config

    @property
    def surface(self) -> RoutingSurfaceConfig:
        return self._surface

    # ── Public ────────────────────────────────────────────────────────────────

    async def route(
        self,
        prompt: str,
        session_id: str,
        *,
        judgment_state: dict | None = None,
    ) -> RoutingEnvelope:
        if not prompt or not prompt.strip():
            raise InvalidPromptError("Prompt must not be empty")

        prompt = prompt.strip()

        if len(self._agent_names) == 1:
            envelope = self._single_agent_envelope(prompt)
        else:
            envelope = await self._score_and_route(prompt, judgment_state)

        if self._store is not None:
            fire_and_forget(
                self._store.write_log(session_id, prompt, envelope),
                label="routing_write_log",
            )
        return envelope

    async def route_forced(
        self,
        prompt: str,
        session_id: str,
        agent_name: str,
        method: str = "forced",
    ) -> RoutingEnvelope:
        """Skip scoring and route to ``agent_name``. The caller gates it: eval, or a screen owner."""
        if agent_name not in get_enabled_agents():
            raise RoutingError(f"Forced agent {agent_name!r} is not an enabled agent")
        prompt = prompt.strip()
        envelope = RoutingEnvelope(
            primary_agent=agent_name,
            confidence=1.0,
            score_gap=0.0,
            routing_method=method,
            is_compound=False,
            subtasks=[
                SubTask(
                    agent=agent_name,
                    prompt=prompt,
                    model=self._full_model(agent_name),
                )
            ],
            requires_synthesis=False,
            raw_scores={agent_name: 1.0},
            threshold=self._config.threshold,
            gap_threshold=self._config.gap_threshold,
        )
        if self._store is not None:
            fire_and_forget(
                self._store.write_log(session_id, prompt, envelope),
                label="routing_write_log",
            )
        return envelope

    # ── Private ───────────────────────────────────────────────────────────────

    def _load_agent_embeddings(self) -> None:
        enabled = get_enabled_agents()
        if not enabled:
            raise RoutingError("No enabled agents found")
        self._agent_names = sorted(enabled.keys())
        descriptions = [enabled[n].description.strip() for n in self._agent_names]
        self._agent_matrix = self._embedder.encode_passage(
            descriptions, normalize_embeddings=True
        )

    def _full_model(self, agent_name: str) -> str:
        return resolve_agent_model(agent_name, "full", self._app_config)

    def _single_agent_envelope(self, prompt: str) -> RoutingEnvelope:
        agent_name = self._agent_names[0]
        model = self._full_model(agent_name)
        return RoutingEnvelope(
            primary_agent=agent_name,
            confidence=1.0,
            score_gap=0.0,
            routing_method="embedding",
            is_compound=False,
            subtasks=[SubTask(agent=agent_name, prompt=prompt, model=model)],
            requires_synthesis=False,
            raw_scores={agent_name: 1.0},
            threshold=self._config.threshold,
            gap_threshold=self._config.gap_threshold,
        )

    async def _judge(
        self, state: dict | None, ranked: list[str]
    ) -> tuple[Judgment | None, RoutingDecision | None]:
        surface = self._surface
        if state is None or len(ranked) < 2:
            return None, None
        if gate(surface, self._system_one) is not None:
            return None, None

        enabled = get_enabled_agents()
        names = shortlist([n for n in ranked if n in enabled], surface.shortlist_k)
        if len(names) < 2:
            return None, None
        questions = build_questions({n: criterion_for(enabled[n]) for n in names})
        return await judge(
            self._system_one,
            surface,
            state,
            questions,
            decide=lambda result: decide(result, surface, names),
            read=read_decision,
        )

    def _envelope(
        self,
        prompt: str,
        *,
        primary: str,
        compound: bool,
        confidence: float,
        score_gap: float,
        raw_scores: dict[str, float],
        judgment: Judgment | None,
    ) -> RoutingEnvelope:
        model = self._full_model(primary)
        return RoutingEnvelope(
            primary_agent=primary,
            confidence=confidence,
            score_gap=score_gap,
            routing_method="embedding",
            is_compound=compound,
            subtasks=[SubTask(agent=primary, prompt=prompt, model=model)],
            requires_synthesis=False,
            raw_scores=raw_scores,
            judgment=judgment,
            threshold=self._config.threshold,
            gap_threshold=self._config.gap_threshold,
        )

    async def _score_and_route(
        self, prompt: str, judgment_state: dict | None = None
    ) -> RoutingEnvelope:
        prompt_vec = self._embedder.encode_query(prompt, normalize_embeddings=True)
        scores: list[float] = (self._agent_matrix @ prompt_vec).tolist()
        raw_scores = dict(zip(self._agent_names, scores))

        sorted_pairs = sorted(raw_scores.items(), key=lambda x: x[1], reverse=True)
        top_agent, top_score = sorted_pairs[0]
        second_score = sorted_pairs[1][1]
        score_gap = top_score - second_score

        judgment, decision = await self._judge(
            judgment_state, [name for name, _ in sorted_pairs]
        )
        common = dict(
            score_gap=score_gap,
            raw_scores=raw_scores,
            judgment=judgment,
        )

        if decision is not None and decision.kind == "trust":
            primary = decision.agent or top_agent
            if primary != top_agent:
                log.info(
                    "routing_choice_disagrees_e5",
                    e5_top=top_agent,
                    choice=primary,
                    peakedness=round(decision.confidence or 0.0, 3),
                )
            return self._envelope(
                prompt,
                primary=primary,
                compound=False,
                confidence=decision.confidence or 0.0,
                **common,
            )
        if decision is not None and decision.kind == "decompose":
            log.info(
                "routing_choice_decompose",
                reason=decision.reason,
                peakedness=round(decision.confidence or 0.0, 3),
            )
            return self._envelope(
                prompt,
                primary=top_agent,
                compound=True,
                confidence=decision.confidence or 0.0,
                **common,
            )

        cfg = self._config
        compound = top_score < cfg.threshold or score_gap < cfg.gap_threshold
        if compound:
            log.info(
                "routing_low_confidence",
                top_score=round(top_score, 3),
                score_gap=round(score_gap, 3),
                reason="below_threshold" if top_score < cfg.threshold else "low_gap",
            )
        # Compound only signals the graph that LLM decomposition is needed;
        # the `decompose` node owns the fallback.decompose() call.
        return self._envelope(
            prompt,
            primary=top_agent,
            compound=compound,
            confidence=top_score,
            **common,
        )
