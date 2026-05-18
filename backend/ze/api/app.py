import signal
from contextlib import asynccontextmanager

from aiogram import Bot
from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from ze.api.openapi import OPENAPI_TAGS
from ze.api.routes import capabilities, memory, routing
from ze.api.telegram import router as telegram_router
from ze.agents.bootstrap import bootstrap_agents
from ze.capability.gate import CapabilityGate
from ze.db import create_checkpointer_pool, create_pool, dispose_checkpointer_pool
from ze.embeddings import get_embedder
from ze.logging import configure_logging, get_logger
from ze.memory.store import MemoryStore
from ze.openrouter.client import OpenRouterClient
from ze.orchestration.graph import build_graph
from ze.routing.router import EmbeddingRouter
from ze.settings import get_settings
from ze.telegram.bot import ZeBot
from ze.telegram.session import ActiveSessionStore

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    pool = await create_pool(settings)
    checkpointer_pool = await create_checkpointer_pool(settings)
    embedder = get_embedder()

    checkpointer = AsyncPostgresSaver(checkpointer_pool)
    await checkpointer.setup()

    openrouter_client = OpenRouterClient(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        logger=get_logger("ze.openrouter"),
        http_referer=settings.openrouter_http_referer,
        title=settings.openrouter_title,
    )

    router = EmbeddingRouter(
        embedder=embedder,
        openrouter_client=openrouter_client,
        db_pool=pool,
        settings=settings,
    )

    capability_gate = CapabilityGate(config_path=settings.capabilities_path)
    memory_store = MemoryStore(
        pool=pool,
        embedder=embedder,
        openrouter_client=openrouter_client,
        settings=settings,
    )
    bootstrap_agents(openrouter_client=openrouter_client, settings=settings)
    graph = build_graph(checkpointer=checkpointer)

    bot = Bot(token=settings.telegram_bot_token)
    if settings.telegram_bot_token and settings.public_url:
        await bot.set_webhook(
            url=f"{settings.public_url}/telegram/webhook",
            secret_token=settings.telegram_webhook_secret,
            allowed_updates=["message", "callback_query"],
        )
        log.info("telegram_webhook_registered", url=settings.public_url)

    ze_bot = ZeBot(
        bot=bot,
        graph=graph,
        store=ActiveSessionStore(),
        router=router,
        capability_gate=capability_gate,
        memory_store=memory_store,
        openrouter_client=openrouter_client,
        embedder=embedder,
        settings=settings,
    )

    app.state.settings = settings
    app.state.pool = pool
    app.state.embedder = embedder
    app.state.graph = graph
    app.state.openrouter_client = openrouter_client
    app.state.router = router
    app.state.capability_gate = capability_gate
    app.state.memory_store = memory_store
    app.state.ze_bot = ze_bot

    signal.signal(signal.SIGHUP, lambda *_: capability_gate.reload())

    log.info("ze_startup_complete")
    yield

    log.info("ze_shutdown")
    await bot.session.close()
    await openrouter_client.aclose()
    await dispose_checkpointer_pool(checkpointer_pool)
    await pool.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Ze API",
        version="0.1.0",
        description=(
            "Personal AI assistant API. REST endpoints manage capabilities, memory, "
            "and routing logs. Chat is handled by the Telegram bot."
        ),
        lifespan=lifespan,
        openapi_tags=OPENAPI_TAGS,
    )

    app.include_router(capabilities.router, prefix="/capabilities")
    app.include_router(memory.router, prefix="/memory")
    app.include_router(routing.router, prefix="/routing")
    app.include_router(telegram_router)

    return app


app = create_app()
