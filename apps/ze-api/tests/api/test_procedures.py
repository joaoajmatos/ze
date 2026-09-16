from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ze_api.api import dependencies
from ze_api.api.routes import procedures
from ze_agents.claims import Provenance
from ze_memory.procedures.admission import ProcedureAdmissionService
from ze_memory.procedures.store import InMemoryProcedureStore
from ze_memory.procedures.types import ProcedureCandidate, ProcedureSourceKind
from ze_plugin.contribution import EvidenceRef


def _client(service):
    app = FastAPI()
    app.state.container = SimpleNamespace(procedure_admission=service)
    app.include_router(procedures.router, prefix="/api/v0")
    app.dependency_overrides[dependencies.require_api_key] = lambda: None
    return TestClient(app)


async def test_list_and_review_procedure_candidate():
    service = ProcedureAdmissionService(InMemoryProcedureStore())
    saved = await service.submit_procedure_candidate(
        ProcedureCandidate(
            source_kind=ProcedureSourceKind.GOAL,
            provenance=Provenance.SYNTHESIZED,
            name="Weekly review",
            trigger="friday",
            preconditions=[],
            steps=["read notes"],
            success_criteria=["plan written"],
            evidence_refs=[EvidenceRef(kind="goal", id=uuid4())],
        )
    )
    client = _client(service)
    listed = client.get("/api/v0/procedures/candidates")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == str(saved.id)
    reviewed = client.post(
        f"/api/v0/procedures/candidates/{saved.id}/review",
        json={"decision": "approve", "reason": "complete"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["version"]["status"] == "active"
    active = client.get("/api/v0/procedures")
    assert len(active.json()) == 1
    procedure_id = reviewed.json()["version"]["procedure_id"]
    disabled = client.post(
        f"/api/v0/procedures/{procedure_id}/disable",
        json={"reason": "stop"},
    )
    assert disabled.status_code == 200
    assert client.get("/api/v0/procedures").json() == []


async def test_library_detail_edit_and_disable():
    service = ProcedureAdmissionService(InMemoryProcedureStore())
    saved = await service.submit_procedure_candidate(
        ProcedureCandidate(
            source_kind=ProcedureSourceKind.GOAL,
            provenance=Provenance.SYNTHESIZED,
            name="Weekly review",
            trigger="friday",
            preconditions=[],
            steps=["read notes"],
            success_criteria=["plan written"],
            evidence_refs=[EvidenceRef(kind="goal", id=uuid4())],
        )
    )
    client = _client(service)
    reviewed = client.post(
        f"/api/v0/procedures/candidates/{saved.id}/review",
        json={"decision": "approve", "reason": "complete"},
    )
    procedure_id = reviewed.json()["version"]["procedure_id"]
    library = client.get("/api/v0/procedures/library")
    assert library.status_code == 200
    assert library.json()[0]["identity_status"] == "active"
    detail = client.get(f"/api/v0/procedures/{procedure_id}")
    assert detail.status_code == 200
    assert detail.json()["versions"][0]["evidence_refs"]
    edited = client.post(
        f"/api/v0/procedures/{procedure_id}/edit",
        json={
            "name": "Weekly review",
            "trigger": "thursday",
            "preconditions": [],
            "steps": ["read notes", "write plan"],
            "success_criteria": ["plan written"],
            "limits": [],
            "reason": "shift day",
        },
    )
    assert edited.status_code == 200
    assert edited.json()["version"]["trigger"] == "thursday"
    disabled = client.post(
        f"/api/v0/procedures/{procedure_id}/disable",
        json={"reason": "stop"},
    )
    assert disabled.status_code == 200
    assert client.get("/api/v0/procedures").json() == []
    library_after = client.get("/api/v0/procedures/library").json()
    assert library_after[0]["identity_status"] == "retired"
