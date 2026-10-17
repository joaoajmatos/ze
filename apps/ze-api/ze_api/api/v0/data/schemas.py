from __future__ import annotations

from pydantic import (
    BaseModel,
)


class DataDomainItem(BaseModel):
    name: str
    importable: bool
    count: int | None
    size_bytes: int


class DataDomainsResponse(BaseModel):
    domains: list[DataDomainItem]
    schema_revisions: list[str]
    total_records: int
    total_size_bytes: int


class DeleteIntentResponse(BaseModel):
    confirmation_token: str
    expires_at: str


class DeleteRequest(BaseModel):
    confirmation_token: str


class ImportResponse(BaseModel):
    domains_imported: list[str]
    rows_imported: dict[str, int]
