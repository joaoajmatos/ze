from __future__ import annotations

from typing import Any

from ze_agents.client import LLMClient
from ze_agents.system_one import SystemOneResult
from ze_agents.errors import InvalidPromptError, RoutingError
from ze_agents.model_resolution import resolve_model
from ze_logging import get_logger
from ze_agents.registry import get_enabled_agents
from ze_agents.tasks import fire_and_forget
from ze_core.routing.complexity import ComplexityEstimator
from ze_core.routing.judge import (
    RoutingDecision,
    RoutingSurfaceConfig,
    build_questions,
    decide,
    shortlist,
)
from ze_core.routing.store import RoutingStore
from ze_core.routing.types import (
    RouterConfig,
    RoutingEnvelope,
    RoutingJudgment,
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
        estimator: ComplexityEstimator | None = None,
        app_config: dict | None = None,
        system_one_client: Any = None,
        surface: RoutingSurfaceConfig | None = None,
    ) -> None:
        self._embedder = embedder
        self._client = openrouter_client
        self._store = routing_store
        self._config = config or RouterConfig()
        self._estimator = estimator or ComplexityEstimator()
        self._app_config = app_config or {}
        self._system_one = system_one_client
        self._surface = surface or RoutingSurfaceConfig()

        self._agent_names: list[str] = []
        self._agent_matrix: Any = None
        self._load_agent_embeddings()

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

    def _resolve_model(self, agent_name: str, complexity: str) -> str:
        enabled = get_enabled_agents()
        agent_cls = enabled.get(agent_name)
        if agent_cls is None:
            declared = None
        elif complexity == "simple" and agent_cls.model_simple:
            declared = agent_cls.model_simple
        else:
            declared = agent_cls.model
        return resolve_model(agent_name, declared, self._app_config)

    def _primary_intent(self, agent_name: str) -> str:
        enabled = get_enabled_agents()
        agent_cls = enabled.get(agent_name)
        if agent_cls is None:
            return "read"
        return next(iter(getattr(agent_cls, "intents", {})), "read")

    def _single_agent_envelope(self, prompt: str) -> RoutingEnvelope:
        agent_name = self._agent_names[0]
        intent = self._primary_intent(agent_name)
        complexity = self._estimator.classify(prompt, intent, 1.0)
        model = self._resolve_model(agent_name, complexity)
        return RoutingEnvelope(
            primary_agent=agent_name,
            confidence=1.0,
            score_gap=0.0,
            routing_method="embedding",
            is_compound=False,
            subtasks=[
                SubTask(agent=agent_name, intent=intent, prompt=prompt, model=model)
            ],
            requires_synthesis=False,
            raw_scores={agent_name: 1.0},
            complexity=complexity,
        )

    async def _judge(
        self, state: dict | None, ranked: list[str]
    ) -> tuple[RoutingJudgment | None, RoutingDecision | None]:
        surface = self._surface
        if state is None or self._system_one is None or len(ranked) < 2:
            return None, None
        if not surface.calibrated:
            if surface.enabled:
                log.warning("routing_surface_uncalibrated")
            return None, None

        enabled = get_enabled_agents()
        names = shortlist([n for n in ranked if n in enabled], surface.shortlist_k)
        if len(names) < 2:
            return None, None
        questions = build_questions({n: enabled[n].description for n in names})
        try:
            result = await self._system_one.evaluate(state, questions, max_attempts=1)
        except Exception as exc:
            log.warning("routing_judgment_error", error=str(exc))
            result = SystemOneResult(outcome="skip", skip_reason="error")

        decision = decide(result, surface, names)
        judgment = RoutingJudgment(
            result=result,
            question_kinds={qid: q.type for qid, q in questions.items()},
            consumed=decision.consumed,
            skip_reason=(
                decision.reason
                if decision.kind == "skip" and result.outcome == "ok"
                else None
            ),
        )
        return judgment, decision

    def _envelope(
        self,
        prompt: str,
        *,
        primary: str,
        compound: bool,
        confidence: float,
        score_gap: float,
        top_score: float,
        raw_scores: dict[str, float],
        decision: RoutingDecision | None,
        judgment: RoutingJudgment | None,
    ) -> RoutingEnvelope:
        intent = self._primary_intent(primary)
        if decision is not None and decision.complexity is not None:
            complexity, source = decision.complexity, "score"
        else:
            complexity, source = (
                self._estimator.classify(prompt, intent, top_score),
                "regex",
            )
        model = self._resolve_model(primary, complexity)
        return RoutingEnvelope(
            primary_agent=primary,
            confidence=confidence,
            score_gap=score_gap,
            routing_method="embedding",
            is_compound=compound,
            subtasks=[
                SubTask(agent=primary, intent=intent, prompt=prompt, model=model)
            ],
            requires_synthesis=False,
            raw_scores=raw_scores,
            complexity=complexity,
            judgment=judgment,
            complexity_source=source,
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
            top_score=top_score,
            raw_scores=raw_scores,
            decision=decision,
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
