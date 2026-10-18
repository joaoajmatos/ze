from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from ze_components import UI_CONTRACT_VERSION


class PluginPageResponse(BaseModel):
    title: str
    tree: list[dict[str, Any]]
    ui_version: str = UI_CONTRACT_VERSION
