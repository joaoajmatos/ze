from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ze_sdk.api import require_api_key
from ze_news.api.schemas import PluginPageResponse
from ze_news.ui.settings import build_news_settings

router = APIRouter(
    prefix="/api/v0", tags=["news"], dependencies=[Depends(require_api_key)]
)


@router.get(
    "/news/settings",
    response_model=PluginPageResponse,
    operation_id="getNewsSettings",
    summary="News settings panel",
    description="Returns the server-driven UI tree for the news settings section.",
)
async def get_news_settings(request: Request) -> PluginPageResponse:
    settings = request.app.state.settings
    news_cfg = (
        settings.config.get("news", {}) if getattr(settings, "config", None) else {}
    )
    if not news_cfg.get("enabled", True) or not news_cfg.get("sources"):
        news_cfg = None
    return PluginPageResponse(title="News", tree=build_news_settings(news_cfg))
