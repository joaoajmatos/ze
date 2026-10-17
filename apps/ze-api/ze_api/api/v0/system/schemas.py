from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
)


class HealthResponse(BaseModel):
    status: Literal["ok"]


class UiContributionSchema(BaseModel):
    id: str
    plugin: str
    kind: Literal["nav", "settings_section"]
    label: str
    icon: str
    path: str | None = None
    page_operation_id: str | None = None
    settings_operation_id: str | None = None
    priority: int = 100
    show_in_mobile_nav: bool = True


class UiManifestResponse(BaseModel):
    nav: list[UiContributionSchema]
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
                path=item.path,
                page_operation_id=item.page_operation_id,
                settings_operation_id=item.settings_operation_id,
                priority=item.priority,
                show_in_mobile_nav=item.show_in_mobile_nav,
            )

        return cls(
            nav=[to_schema(item) for item in manifest.nav],
            settings_sections=[to_schema(item) for item in manifest.settings_sections],
        )


class VersionResponse(BaseModel):
    api_version: str
    client_version: str
