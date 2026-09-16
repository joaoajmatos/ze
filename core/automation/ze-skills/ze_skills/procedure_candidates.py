from __future__ import annotations

from ze_agents.claims import Provenance
from ze_plugin.contribution import EvidenceRef

from ze_memory.procedures.types import ProcedureCandidate, ProcedureSourceKind
from ze_skills.types import Skill


def candidate_from_skill(skill: Skill) -> ProcedureCandidate:
    steps = [
        line.strip().lstrip("-* ").strip()
        for line in skill.instructions.splitlines()
        if line.strip()
    ]
    if not steps:
        steps = [skill.instructions.strip() or skill.description]
    evidence = [EvidenceRef(kind="goal", id=skill.id)] if skill.id else []
    return ProcedureCandidate(
        source_kind=ProcedureSourceKind.SKILL,
        provenance=Provenance.PROMPT_SUPPLIED,
        name=skill.name,
        trigger=skill.description or skill.name,
        preconditions=[],
        steps=steps[:20],
        success_criteria=[skill.description or "skill instructions remain accurate"],
        evidence_refs=evidence,
    )
