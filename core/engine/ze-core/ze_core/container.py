from __future__ import annotations

import asyncio
import importlib
import inspect
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, get_args, get_type_hints

from ze_agents.errors import AgentConfigError, RoutingError
from ze_agents.interface.types import RawInput
from ze_logging import get_logger
from ze_agents.types import AbortToken
from langgraph.types import Command

from ze_core.conversation import make_graph_input
from ze_core.conversation.turn import open_confirmation
from ze_core.routing.factory import build_embedding_router, build_tier_judge
from ze_core.telemetry.context import enter_turn_context

if TYPE_CHECKING:
    from ze_core.routing.router import EmbeddingRouter
    from ze_agents.interface.types import InvokeResult

log = get_logger(__name__)


@dataclass
class Container:
    settings: Any
    pool: Any
    checkpointer_pool: Any
    embedder: Any
    openrouter_client: Any
    router: Any
    memory_store: Any
    memory_consolidator: Any
    graph: Any
    interface: Any = None
    tier_judge: Any = (
        None  # TierJudge | None; absent means every agent runs its full model
    )
    plugins: list = field(default_factory=list)  # list[ZePlugin]
    _abort_tokens: dict = field(default_factory=dict)  # thread_id → AbortToken
    _fact_extractor: Any = None  # ze_memory.extractor.gather_fact_proposals or None
    _turn_extractor: Any = None  # ze_memory.extractor.gather_turn_proposals or None

    def _build_config(self, thread_id: str, **extra: Any) -> dict:
        """Build the LangGraph configurable dict for a conversation thread."""
        plugin_services: dict[str, Any] = {}
        for plugin in self.plugins:
            plugin_services.update(plugin.configurable_services())

        return {
            "configurable": {
                "thread_id": thread_id,
                "router": self.router,
                "tier_judge": self.tier_judge,
                "openrouter_client": self.openrouter_client,
                "memory_store": self.memory_store,
                "fact_extractor": self._fact_extractor,
                "turn_extractor": self._turn_extractor,
                **plugin_services,
                **extra,
            }
        }

    async def invoke(
        self,
        prompt: str,
        thread_id: str,
        *,
        audio_data: bytes | None = None,
        audio_mime: str | None = None,
        image_data: bytes | None = None,
        image_mime: str | None = None,
        messages: list[dict] | None = None,
    ) -> "InvokeResult":
        """Run a full conversation turn, handling the confirmation loop.

        For **inline** confirmation: calls interface.confirm(), resumes the
        graph with the answer, and delivers the final response via interface.send().

        For **async** confirmation: calls interface.send_confirmation() and
        returns InvokeResult(confirmation_pending=True). The caller must invoke
        Container.resume() once the user decision arrives.

        If no interface is configured, the graph is invoked once and
        final_response is returned directly without any delivery call.
        """
        from ze_agents.interface.types import (
            ConfirmationRequest,
            InvokeResult,
            OutboundMessage,
        )

        graph_input = make_graph_input(
            RawInput(
                text=prompt,
                audio=audio_data,
                audio_mime=audio_mime,
                image=image_data,
                image_mime=image_mime,
            ),
            thread_id,
        )
        # Only overwrite the checkpointed history when the caller supplies one;
        # otherwise the prior turns persist and write_memory keeps appending.
        if messages is not None:
            graph_input["messages"] = messages
        enter_turn_context(thread_id)
        abort_token = AbortToken()
        self._abort_tokens[thread_id] = abort_token
        config = self._build_config(thread_id, abort_token=abort_token)

        try:
            state = await self.graph.ainvoke(graph_input, config)

            if state.get("error"):
                return InvokeResult(session_id=thread_id, error=state["error"])

            snapshot = await self.graph.aget_state(config)
            confirmation = open_confirmation(snapshot)
            if confirmation is not None:
                request = ConfirmationRequest(
                    content="\n".join(
                        f"{item.effect_phrase}: {item.summary}".strip(": ")
                        for item in confirmation.items
                    ),
                    options=["Approve", "Cancel"],
                    timeout_seconds=getattr(
                        self.settings, "confirm_timeout_seconds", None
                    ),
                )

                if self.interface is None:
                    return InvokeResult(session_id=thread_id, confirmation_pending=True)

                style = getattr(type(self.interface), "confirmation_style", None)

                if style == "async":
                    await self.interface.send_confirmation(request)
                    return InvokeResult(session_id=thread_id, confirmation_pending=True)

                # inline — block until user responds
                decision = await self.interface.confirm(request)
                choice = "approve" if decision.approved else "deny"
                state = await self.graph.ainvoke(
                    Command(resume={"choice": choice, "edits": {}}), config
                )

            response = state.get("final_response") or ""
            if self.interface and response:
                await self.interface.send(OutboundMessage(content=response))
            return InvokeResult(session_id=thread_id, response=response)
        finally:
            self._abort_tokens.pop(thread_id, None)

    async def abort_invocation(self, thread_id: str, reason: str | None = None) -> None:
        """Signal the agentic loop running under thread_id to stop cleanly.

        No-op if thread_id has no active invocation (already completed or never started).
        """
        token = self._abort_tokens.get(thread_id)
        if token is not None:
            token.abort(reason)

    async def resume(
        self,
        thread_id: str,
        choice: str = "approve",
        edits: dict[str, str] | None = None,
    ) -> "InvokeResult":
        """Answer the confirmation a paused graph is waiting on (async style).

        Called by the transport callback handler once the user has decided.
        """
        from ze_agents.interface.types import InvokeResult, OutboundMessage

        enter_turn_context(thread_id)
        config = self._build_config(thread_id)
        state = await self.graph.ainvoke(
            Command(resume={"choice": choice, "edits": edits or {}}), config
        )

        if state.get("error"):
            return InvokeResult(session_id=thread_id, error=state["error"])

        response = state.get("final_response") or ""
        if self.interface and response:
            await self.interface.send(OutboundMessage(content=response))
        return InvokeResult(session_id=thread_id, response=response)

    async def close(self) -> None:
        from ze_agents.registry import get_enabled_instances

        for instance in get_enabled_instances().values():
            try:
                await instance.shutdown()
            except Exception as exc:
                log.warning(
                    "agent_shutdown_failed",
                    agent=getattr(instance, "name", "?"),
                    error=str(exc),
                )

        await self.openrouter_client.aclose()
        aclose = getattr(self.memory_store, "aclose", None)
        if callable(aclose):
            import asyncio

            if asyncio.iscoroutinefunction(aclose):
                await aclose()
        await _dispose_pool(self.checkpointer_pool)
        await _dispose_pool(self.pool)
        log.info("container_closed")

    @classmethod
    async def from_config(
        cls,
        config_path: Path,
        deps: dict[type, Any] | None = None,
        interface: Any = None,
        plugins: list | None = None,
    ) -> "Container":
        config_path = Path(config_path)
        app_root = config_path.parent

        # 0. Validate interface early so misconfiguration fails fast
        if interface is not None:
            from ze_agents.interface.validation import validate_interface

            validate_interface(interface)

        # 1. Load Settings
        from ze_agents.settings import Settings

        settings = Settings.from_env(config_path)

        # 2. Create database pools / connections
        is_sqlite = settings.database_url.lower().startswith("sqlite")

        if is_sqlite:
            pool = None
            checkpointer_pool = None
        else:
            import asyncpg  # type: ignore[import]

            pool = await asyncpg.create_pool(settings.database_url)
            checkpointer_pool = await asyncpg.create_pool(settings.database_url)

        # 3. Load embedder (sentence_transformers)
        from ze_core.embeddings import get_embedder

        _embedding_model = settings.config.get("models", {}).get("embedding")
        embedder = (
            get_embedder(_embedding_model) if _embedding_model else get_embedder()
        )
        from ze_core.nli import LocalNLIClient

        nli_client = LocalNLIClient()

        # 4. Build OpenRouterClient
        from ze_core.openrouter.client import OpenRouterClient

        openrouter_client = OpenRouterClient(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            logger=log,
        )

        from ze_agents.system_one import SystemOneClient

        from ze_core.openrouter.system_one import build_system_one_client

        system_one_client = build_system_one_client(settings)

        # 5. Discover agent modules
        package = _infer_package(app_root)
        _discover_agents(app_root, package)

        # 6. Validate registered agent classes
        _validate_registry(settings)

        # 7. Instantiate enabled agents
        from ze_agents.registry import get_enabled_agents

        from ze_agents.db import DBPool

        internal_deps: dict[type, Any] = {
            Settings: settings,
            DBPool: pool,
            OpenRouterClient: openrouter_client,
            SystemOneClient: system_one_client,
        }
        merged = {**internal_deps, **(deps or {})}
        instances = _instantiate_agents(get_enabled_agents(), merged)

        # 8. Call startup() on all instances concurrently
        await asyncio.gather(
            *[inst.startup() for inst in instances.values()],
            return_exceptions=True,
        )

        # 9. Build EmbeddingRouter
        _validate_model_config(settings)

        router = _build_router(
            settings=settings,
            embedder=embedder,
            openrouter_client=openrouter_client,
            pool=pool,
            system_one_client=system_one_client,
        )
        tier_judge = _build_tier_judge(
            settings=settings, system_one_client=system_one_client
        )

        # 11. Build MemoryStore and MemoryConsolidator
        from ze_memory.extractor import (
            gather_fact_proposals,
            gather_turn_proposals,
        )
        from ze_memory.retriever import PostgresMemoryStore

        if is_sqlite:
            memory_store = PostgresMemoryStore(
                pool=pool,
                embedder=embedder,
                openrouter_client=openrouter_client,
                settings=settings,
                nli_client=nli_client,
            )
            memory_consolidator = None
        else:
            from ze_memory.consolidation_store import PostgresConsolidationStore
            from ze_memory.consolidator import MemoryConsolidator

            memory_store = PostgresMemoryStore(
                pool=pool,
                embedder=embedder,
                openrouter_client=openrouter_client,
                settings=settings,
                nli_client=nli_client,
            )
            memory_consolidator = MemoryConsolidator(
                store=PostgresConsolidationStore(pool),
                embedder=embedder,
                openrouter_client=openrouter_client,
                settings=settings,
                nli_client=nli_client,
            )

        # 12. Build LangGraph checkpointer and compile graph
        from ze_core.orchestration.graph import build_graph

        resolved_plugins = plugins or []
        if is_sqlite:
            from langgraph.checkpoint.memory import MemorySaver  # type: ignore[import]

            checkpointer = MemorySaver()
        else:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # type: ignore[import]
            from ze_core.checkpoint_serde import build_checkpoint_serde

            serde = build_checkpoint_serde(resolved_plugins)
            checkpointer = AsyncPostgresSaver(checkpointer_pool, serde=serde)
            await checkpointer.setup()

        graph = build_graph(checkpointer, plugins=resolved_plugins)

        log.info("container_ready", agents=list(instances.keys()))
        return cls(
            settings=settings,
            pool=pool,
            checkpointer_pool=checkpointer_pool,
            embedder=embedder,
            openrouter_client=openrouter_client,
            router=router,
            tier_judge=tier_judge,
            memory_store=memory_store,
            memory_consolidator=memory_consolidator,
            graph=graph,
            interface=interface,
            plugins=resolved_plugins,
            _fact_extractor=gather_fact_proposals,
            _turn_extractor=gather_turn_proposals,
        )


# ── private helpers ───────────────────────────────────────────────────────────


def _build_router(
    *,
    settings: Any,
    embedder: Any,
    openrouter_client: Any,
    pool: Any,
    system_one_client: Any,
) -> EmbeddingRouter:
    from ze_core.routing.store import PostgresRoutingStore

    return build_embedding_router(
        embedder=embedder,
        openrouter_client=openrouter_client,
        config=settings.config,
        system_one_client=system_one_client,
        routing_store=PostgresRoutingStore(pool) if pool is not None else None,
    )


def _build_tier_judge(*, settings: Any, system_one_client: Any):
    return build_tier_judge(config=settings.config, system_one_client=system_one_client)


def _discover_agents(app_root: Path, package: str) -> None:
    agents_dir = app_root / "agents"
    if not agents_dir.exists():
        raise AgentConfigError(f"agents/ directory not found at {agents_dir}")

    for subdir in sorted(agents_dir.iterdir()):
        if subdir.is_dir() and (subdir / "agent.py").exists():
            module_path = f"{package}.agents.{subdir.name}.agent"
            importlib.import_module(module_path)


def _validate_registry(settings: Any) -> None:
    """Validate tool names against the tool registry (name and description
    are already validated by @agent at decoration time)."""
    from ze_agents.registry import get_registered_agents
    from ze_agents.tool import registered_tools, validate_tool_declarations

    validate_tool_declarations()
    tool_reg = registered_tools()
    registered = get_registered_agents()

    for name, cls in registered.items():
        for tool_name in getattr(cls, "tools", []):
            if tool_name not in tool_reg:
                raise AgentConfigError(
                    f"Agent {name!r} declares unknown tool {tool_name!r}"
                )

    enabled = {n: c for n, c in registered.items() if getattr(c, "enabled", True)}
    if not enabled:
        raise RoutingError("No enabled agents found after discovery")


def _validate_model_config(settings: Any) -> None:
    """Fail fast at startup if `models.default`/`models.overrides` are malformed."""
    from ze_agents.model_resolution import KNOWN_STEP_KEYS, validate_model_config
    from ze_agents.registry import get_enabled_agents

    known_model_keys = frozenset(get_enabled_agents().keys()) | KNOWN_STEP_KEYS
    validate_model_config(settings.config, known_model_keys)


def _optional_inner(annotation: Any) -> Any | None:
    """X for an `X | None` annotation, else None."""
    args = get_args(annotation)
    if type(None) in args and len(args) == 2:
        return next(a for a in args if a is not type(None))
    return None


def _resolve(cls: type, deps: dict[type, Any]) -> Any:
    try:
        hints = get_type_hints(cls.__init__)
    except Exception:
        hints = {}

    sig = inspect.signature(cls.__init__)
    kwargs: dict[str, Any] = {}

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        annotation = hints.get(param_name)
        if annotation is None:
            raise AgentConfigError(
                f"{cls.__name__}.__init__ parameter {param_name!r} has no type annotation"
            )
        optional_inner = _optional_inner(annotation)
        if optional_inner is not None:
            kwargs[param_name] = deps.get(optional_inner)
            continue
        if annotation not in deps:
            raise AgentConfigError(
                f"No dependency registered for {annotation!r}"
                f" (required by {cls.__name__})."
                " Add it to deps before calling from_config()."
            )
        kwargs[param_name] = deps[annotation]

    return cls(**kwargs)


def _instantiate_agents(
    registered: dict[str, Any],
    deps: dict[type, Any],
) -> dict[str, Any]:
    from ze_agents.registry import register_instance

    instances: dict[str, Any] = {}
    for name, cls in registered.items():
        if not getattr(cls, "enabled", True):
            continue
        instance = _resolve(cls, deps)
        register_instance(name, instance)
        instances[name] = instance
    return instances


def _infer_package(app_root: Path) -> str:
    resolved = app_root.resolve()
    for entry in sys.path:
        if not entry:
            continue
        try:
            rel = resolved.relative_to(Path(entry).resolve())
            if rel.parts:
                return rel.parts[0]
        except ValueError:
            continue
    return app_root.name


def _sqlite_db_path(url: str) -> str:
    """Extract the file path from a sqlite:// URL.

    sqlite:///./app.db   -> ./app.db
    sqlite:////abs/p.db  -> /abs/p.db
    sqlite:///:memory:   -> :memory:
    """
    # Strip the sqlite:// or sqlite:/// prefix
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///") :]
    if url.startswith("sqlite://"):
        return url[len("sqlite://") :]
    return url


async def _dispose_pool(pool: Any) -> None:
    if pool is None:
        return
    try:
        await pool.close()
    except Exception as exc:
        log.warning("pool_close_failed", error=str(exc))
