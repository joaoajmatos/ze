from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ze_api.api.openapi import OPENAPI_TAGS
from ze_api.api.eval import dev_router
from ze_api.api.v0 import router as v0_router
from ze_api.api.ws import router as ws_router
from ze_api.lifespan import lifespan
from ze_api.settings import get_settings


def _parse_cors_origins(value: str) -> list[str]:
    if value.strip() == "*":
        return ["*"]
    return [origin.strip() for origin in value.split(",") if origin.strip()]


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

    app.include_router(v0_router)

    # WebSocket — auth handled by the WS handshake
    app.include_router(ws_router)

    # Eval and debug surfaces: mounted only when the server runs with EVAL_MODE
    if settings.eval_mode:
        app.include_router(dev_router)

    return app


app = create_app()
