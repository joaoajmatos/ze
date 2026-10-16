from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class PluginPageResponse(BaseModel):
    title: str
    tree: list[dict[str, Any]]
