from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
)


class HealthResponse(BaseModel):
    status: Literal["ok"]


class UiContributionSchema(BaseModel):
    id: str
    plugin: str
    kind: Literal["module", "preset", "settings_section"]
    label: str
    icon: str
    slot: Literal["mind.entity", "doing.run", "governance.connections"] | None = None
    prompt: str | None = None
    settings_operation_id: str | None = None
    priority: int = 100


class UiManifestResponse(BaseModel):
    modules: list[UiContributionSchema]
    presets: list[UiContributionSchema]
    settings_sections: list[UiContributionSchema]

    @classmethod
    def from_domain(cls, manifest) -> UiManifestResponse:
        def to_schema(item) -> UiContributionSchema:
            return UiContributionSchema(
                id=item.id,
                plugin=item.plugin,
                kind=item.kind,
                label=item.label,
                icon=item.icon,
                slot=item.slot,
                prompt=item.prompt,
                settings_operation_id=item.settings_operation_id,
                priority=item.priority,
            )

        return cls(
            modules=[to_schema(item) for item in manifest.modules],
            presets=[to_schema(item) for item in manifest.presets],
            settings_sections=[to_schema(item) for item in manifest.settings_sections],
        )


class UiModuleResponse(BaseModel):
    module_id: str
    applies: bool
    components: list[dict[str, Any]]
    ui_version: str


class VersionResponse(BaseModel):
    api_version: str
    client_version: str


class AgentModelSetting(BaseModel):
    name: str
    model: str
    model_simple: str | None


class ModelSettingsResponse(BaseModel):
    complexity_enabled: bool
    simple_max: float | None
    agents: list[AgentModelSetting]
