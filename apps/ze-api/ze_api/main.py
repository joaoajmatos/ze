from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ze_api.api.openapi import OPENAPI_TAGS
from ze_api.api.routes import (
    activity,
    collisions,
    costs,
    data,
    eval,
    feedback,
    goals,
    health,
    loops,
    memory,
    notifications,
    priority,
    procedures,
    routing,
    sessions,
    skills,
    ui,
    version,
    webhooks,
    held_writes,
    workflows,
    workspace,
)
from ze_api.api.ws import router as ws_router
from ze_api.api.messages import router as messages_router
from ze_api.lifespan import lifespan
from ze_api.settings import get_settings


def _parse_cors_origins(value: str) -> list[str]:
    if value.strip() == "*":
        return ["*"]
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def _include_dev_routers(app: FastAPI) -> None:
    """Eval and debug surfaces: mounted only when the server runs with EVAL_MODE."""
    app.include_router(eval.router)
    app.include_router(collisions.router, prefix="/api/v0")
    app.include_router(routing.router, prefix="/api/v0/routing")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Ze API",
        version="0.1.0",
        description=(
            "Personal AI assistant API. REST endpoints manage memory, "
            "and routing logs. Chat is handled via WebSocket at /ws."
        ),
        lifespan=lifespan,
        openapi_tags=OPENAPI_TAGS,
        openapi_components={
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "ApiKey",
                }
            }
        },
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_parse_cors_origins(settings.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Public — no auth required
    app.include_router(version.router)
    app.include_router(health.router, prefix="/api/v0")

    # WebSocket — auth handled by the WS handshake
    app.include_router(ws_router)

    # Versioned REST API
    app.include_router(activity.router, prefix="/api/v0")
    app.include_router(memory.router, prefix="/api/v0/memory")
    app.include_router(workflows.router, prefix="/api/v0/workflows")
    app.include_router(costs.router, prefix="/api/v0/costs")
    app.include_router(goals.router, prefix="/api/v0")
    app.include_router(held_writes.router, prefix="/api/v0")
    app.include_router(sessions.router, prefix="/api/v0")
    app.include_router(messages_router, prefix="/api/v0")
    app.include_router(feedback.router, prefix="/api/v0")
    app.include_router(data.router, prefix="/api/v0")
    app.include_router(notifications.router, prefix="/api/v0")
    app.include_router(loops.router, prefix="/api/v0")
    app.include_router(priority.router, prefix="/api/v0")
    app.include_router(procedures.router, prefix="/api/v0")
    app.include_router(skills.router, prefix="/api/v0")
    app.include_router(workspace.router, prefix="/api/v0")
    app.include_router(ui.router)
    app.include_router(webhooks.router)

    if settings.eval_mode:
        _include_dev_routers(app)

    return app


app = create_app()
