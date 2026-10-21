from __future__ import annotations

from pathlib import Path
from typing import Any

import asyncpg
from sentence_transformers import SentenceTransformer

from ze_agents.client import LLMClient
from ze_agents.nli import NLIClient
from ze_logging import get_logger
from ze_sdk import ZePlugin
from ze_sdk.ui import ModuleResult, ModuleSubject, UiContribution
from ze_agents.settings import Settings as CoreSettings
from ze_news.onboarding import NewsOnboardingProvider

log = get_logger(__name__)


class NewsPlugin(ZePlugin):
    def __init__(
        self,
        *,
        pool: asyncpg.Pool,
        embedder: SentenceTransformer,
        settings: CoreSettings,
        openrouter_client: LLMClient,
        nli_client: NLIClient,
    ) -> None:
        from ze_news.store import NewsStore
        from ze_news.registry import build_registry
        from ze_news.jobs.fetch import NewsFetchJob
        from ze_news.types import SourceConfig

        self._pool = pool
        news_cfg = settings.config.get("news", {})
        self._enabled = bool(news_cfg.get("enabled", True) and news_cfg.get("sources"))
        self._store: NewsStore | None = None
        self._fetch_job: NewsFetchJob | None = None
        self._fetch_cron: str = news_cfg.get("fetch_schedule", "*/30 * * * *")
        self._source_count: int = 0

        self._salience_cfg: dict | None = None
        self._news_signal_source: Any = None
        if not self._enabled:
            return

        source_configs = [
            SourceConfig(
                key=s["key"],
                type=s["type"],
                url=s["url"],
                tags=s.get("tags", []),
            )
            for s in news_cfg["sources"]
        ]
        registry = build_registry(source_configs)
        self._store = NewsStore(pool=pool, embedder=embedder)
        self._source_count = len(source_configs)

        credibility_cfg = news_cfg.get("credibility", {})
        nli_credibility_enabled = bool(news_cfg.get("nli_credibility_enabled", False))
        nli_dedup_enabled = bool(news_cfg.get("nli_dedup_enabled", False))
        signals_cfg = settings.config.get("memory", {}).get("signals", {})
        self._force_ingest_sources: list[str] = signals_cfg.get(
            "force_ingest_sources", []
        )
        salience_raw = settings.config.get("correlation", {}).get("salience", {})
        self._salience_cfg = salience_raw if salience_raw else None

        from ze_news.signals import NewsSignalSource

        self._news_signal_source = NewsSignalSource()
        self._fetch_job = NewsFetchJob(
            registry=registry,
            store=self._store,
            retention_days=int(news_cfg.get("retention_days", 7)),
            client=openrouter_client if credibility_cfg.get("enabled", False) else None,
            credibility_enabled=credibility_cfg.get("enabled", False),
            credibility_llm_enabled=credibility_cfg.get("llm_scoring", True),
            credibility_model=credibility_cfg.get("model", "openai/gpt-4o-mini"),
            nli_client=nli_client,
            nli_credibility_enabled=nli_credibility_enabled,
            nli_headline_contradiction_threshold=float(
                news_cfg.get("nli_headline_contradiction_threshold", 0.50)
            ),
            nli_headline_entailment_threshold=float(
                news_cfg.get("nli_headline_entailment_threshold", 0.30)
            ),
            nli_dedup_enabled=nli_dedup_enabled,
            nli_dedup_cosine_threshold=float(
                news_cfg.get("nli_dedup_cosine_threshold", 0.75)
            ),
            nli_dedup_entailment_threshold=float(
                news_cfg.get("nli_dedup_entailment_threshold", 0.70)
            ),
            min_fetch_interval_minutes=int(
                news_cfg.get("min_fetch_interval_minutes", 30)
            ),
            force_ingest_sources=self._force_ingest_sources,
            signal_source=self._news_signal_source,
        )

    @classmethod
    def migrations_path(cls) -> Path | None:
        return Path(__file__).parent / "migrations"

    def screen_resolvers(self) -> list[Any]:
        if self._store is None:
            return []
        from ze_news.screen_resolvers import build_screen_resolvers

        return build_screen_resolvers(news_store=self._store)

    def rest_stores(self) -> dict[str, Any]:
        if self._store is None:
            return {}
        return {"news_store": self._store}

    def agent_deps(self, accumulated: dict) -> dict:
        if self._store is None:
            return {}
        from ze_news.jobs.fetch import NewsFetchJob
        from ze_news.store import NewsStore

        return {NewsStore: self._store, NewsFetchJob: self._fetch_job}

    def configurable_services(self) -> dict[str, Any]:
        if self._store is None:
            return {}
        return {"news_store": self._store}

    def memory_policies(self) -> dict:
        from ze_sdk.memory import ResearchPolicy

        return {"news": ResearchPolicy()}

    def onboarding(self) -> NewsOnboardingProvider | None:
        if not self._enabled:
            return None
        return NewsOnboardingProvider()

    def signal_sources(self) -> list:
        if self._news_signal_source is None:
            return []
        return [self._news_signal_source]

    def ui_contributions(self) -> list[UiContribution]:
        if not self._enabled:
            return []
        return [
            UiContribution(
                id="ze_news.whats_new",
                plugin="ze_news",
                kind="preset",
                label="What's new in my sources?",
                icon="newspaper",
                prompt="What's new in my sources?",
            ),
            UiContribution(
                id="ze_news.sources",
                plugin="ze_news",
                kind="module",
                label="Sources",
                icon="newspaper",
                slot="mind.entity",
                provider=self._sources_module,
            ),
            UiContribution(
                id="ze_news.settings",
                plugin="ze_news",
                kind="settings_section",
                label="News",
                icon="newspaper",
                settings_operation_id="getNewsSettings",
            ),
        ]

    async def _sources_module(self, subject: ModuleSubject) -> ModuleResult:
        from ze_components import ClaimItem, ClaimPosture, claim_list
        from ze_components.serialize import serialize_tree
        from ze_news import article_ref_id

        if self._store is None or subject.entity_type != "topic" or not subject.label:
            return ModuleResult(applies=False)
        articles = await self._store.by_tag(subject.label)
        if not articles:
            return ModuleResult(applies=False)
        items = [
            ClaimItem(
                text=f"{a.title} · {a.source_key} · {a.published_at.date().isoformat()}",
                claim=ClaimPosture(
                    kind="fact",
                    subject="fact",
                    ref_id=article_ref_id(a.url),
                    source="live_search",
                ),
            )
            for a in articles
        ]
        return ModuleResult(
            applies=True, components=serialize_tree([claim_list(items)])
        )

    def rest_routes(self) -> list:
        if not self._enabled:
            return []
        from ze_news.api.routes import router

        return [router]

    def agent_module_paths(self) -> list[str]:
        if not self._enabled:
            return []
        return ["ze_news.agents.agent"]

    async def startup(self, container: Any) -> None:
        if self._fetch_job is None or self._store is None:
            return

        memory_store = getattr(container, "memory_store", None)
        if memory_store is not None:
            self._fetch_job._memory_store = memory_store

        if memory_store is not None and self._salience_cfg is not None:
            self._fetch_job._admission_gate = self._build_admission_gate(
                memory_store, container
            )

        self._fetch_job.bind_interface(container.interface)
        container.proactive_scheduler.register(self._fetch_job, cron=self._fetch_cron)
        log.info(
            "news_fetch_scheduled",
            cron=self._fetch_cron,
            sources=self._source_count,
        )

    def _build_admission_gate(self, memory_store: Any, container: Any) -> Any:
        from ze_sdk.memory import build_admission_gate

        goal_provider = None
        for plugin in getattr(container, "plugins", []):
            gs = getattr(plugin, "goal_store", None)
            if gs is not None:
                goal_provider = gs
                break

        return build_admission_gate(
            self._salience_cfg, memory_store, goal_provider=goal_provider
        )
