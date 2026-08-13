from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ze_api.api.dependencies import get_skill_store, require_api_key
from ze_api.api.schemas import (
    SkillDetailResponse,
    SkillImportRequest,
    SkillListResponse,
    SkillReferenceFileResponse,
)
from ze_skills import rest as skills_rest
from ze_skills.errors import (
    InvalidSkillTransitionError,
    SkillNotFoundError,
    SkillParseError,
)
from ze_skills.store import SkillStore
from ze_skills.types import SkillSource, SkillStatus

router = APIRouter(
    prefix="/skills", tags=["skills"], dependencies=[Depends(require_api_key)]
)


@router.get(
    "",
    response_model=SkillListResponse,
    operation_id="listSkills",
    summary="List skills",
    description="Return every skill (bundled and imported), optionally filtered by "
    "status and/or source (FR-012).",
)
async def list_skills(
    status: SkillStatus | None = Query(default=None),
    source: SkillSource | None = Query(default=None),
    store: SkillStore = Depends(get_skill_store),
) -> SkillListResponse:
    skills = await skills_rest.list_skills(store, status=status, source=source)
    return SkillListResponse(skills=skills)


@router.get(
    "/{skill_id}",
    response_model=SkillDetailResponse,
    operation_id="getSkill",
    summary="Get skill detail",
    description="Return full detail for one skill, including its instructions, "
    "tool restrictions, reference-file listing, and — when pending re-review after "
    "a content change — the previously-approved version for comparison (FR-005, FR-016).",
)
async def get_skill(
    skill_id: UUID,
    store: SkillStore = Depends(get_skill_store),
) -> SkillDetailResponse:
    try:
        skill = await skills_rest.get_skill(store, skill_id)
    except SkillNotFoundError:
        raise HTTPException(status_code=404, detail="Skill not found")
    return SkillDetailResponse.model_validate(skill)


@router.get(
    "/{skill_id}/reference-files/{filename}",
    response_model=SkillReferenceFileResponse,
    operation_id="getSkillReferenceFile",
    summary="Get a skill's reference file content",
    description="Return the full content of one stored non-script supporting "
    "reference file bundled with an imported skill (FR-022).",
)
async def get_skill_reference_file(
    skill_id: UUID,
    filename: str,
    store: SkillStore = Depends(get_skill_store),
) -> SkillReferenceFileResponse:
    try:
        ref = await skills_rest.get_reference_file(store, skill_id, filename)
    except SkillNotFoundError:
        raise HTTPException(status_code=404, detail="Reference file not found")
    return SkillReferenceFileResponse.model_validate(ref)


@router.post(
    "/import",
    response_model=SkillDetailResponse,
    status_code=201,
    operation_id="importSkill",
    summary="Import a skill from a URL",
    description="Fetch and parse a SKILL.md (optionally bundled in a zip archive) "
    "from a user-submitted URL, creating a pending-review skill. Never activates it "
    "(FR-001-004).",
)
async def import_skill(
    body: SkillImportRequest,
    store: SkillStore = Depends(get_skill_store),
) -> SkillDetailResponse:
    try:
        skill = await skills_rest.import_skill(store, body.url)
    except SkillParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return SkillDetailResponse.model_validate(skill)


@router.post(
    "/{skill_id}/approve",
    response_model=SkillDetailResponse,
    operation_id="approveSkill",
    summary="Approve a pending skill",
    description="Transition a pending-review skill to active (FR-006). Records a "
    "SkillReview row and refreshes eligibility for matching.",
)
async def approve_skill(
    skill_id: UUID,
    store: SkillStore = Depends(get_skill_store),
) -> SkillDetailResponse:
    try:
        skill = await skills_rest.approve(store, skill_id)
    except SkillNotFoundError:
        raise HTTPException(status_code=404, detail="Skill not found")
    except InvalidSkillTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return SkillDetailResponse.model_validate(skill)


@router.post(
    "/{skill_id}/reject",
    response_model=SkillDetailResponse,
    operation_id="rejectSkill",
    summary="Reject a pending skill",
    description="Transition a pending-review skill to rejected (FR-006); it never "
    "becomes active in this form. Records a SkillReview row.",
)
async def reject_skill(
    skill_id: UUID,
    store: SkillStore = Depends(get_skill_store),
) -> SkillDetailResponse:
    try:
        skill = await skills_rest.reject(store, skill_id)
    except SkillNotFoundError:
        raise HTTPException(status_code=404, detail="Skill not found")
    except InvalidSkillTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return SkillDetailResponse.model_validate(skill)


@router.post(
    "/{skill_id}/disable",
    response_model=SkillDetailResponse,
    operation_id="disableSkill",
    summary="Disable an active skill",
    description="Transition an active skill to disabled (FR-013), removing it from "
    "the matcher's active set immediately.",
)
async def disable_skill(
    skill_id: UUID,
    store: SkillStore = Depends(get_skill_store),
) -> SkillDetailResponse:
    try:
        skill = await skills_rest.disable(store, skill_id)
    except SkillNotFoundError:
        raise HTTPException(status_code=404, detail="Skill not found")
    except InvalidSkillTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return SkillDetailResponse.model_validate(skill)


@router.post(
    "/{skill_id}/enable",
    response_model=SkillDetailResponse,
    operation_id="enableSkill",
    summary="Re-enable a disabled skill",
    description="Transition a disabled skill back to active (FR-013). No re-review "
    "required since content hasn't changed; rejected if the skill drifted to "
    "pending_review in the meantime.",
)
async def enable_skill(
    skill_id: UUID,
    store: SkillStore = Depends(get_skill_store),
) -> SkillDetailResponse:
    try:
        skill = await skills_rest.enable(store, skill_id)
    except SkillNotFoundError:
        raise HTTPException(status_code=404, detail="Skill not found")
    except InvalidSkillTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return SkillDetailResponse.model_validate(skill)


@router.delete(
    "/{skill_id}",
    status_code=204,
    operation_id="deleteSkill",
    summary="Remove an imported skill",
    description="Permanently remove an imported skill (FR-014), cascading its "
    "SkillReview/ReferenceFile rows. Bundled skills can't be removed this way — "
    "uninstall the owning plugin instead.",
)
async def delete_skill(
    skill_id: UUID,
    store: SkillStore = Depends(get_skill_store),
) -> None:
    try:
        await skills_rest.remove(store, skill_id)
    except SkillNotFoundError:
        raise HTTPException(status_code=404, detail="Skill not found")
    except InvalidSkillTransitionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
