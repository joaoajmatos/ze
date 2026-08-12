# Phase 1 Data Model: Agent Skills

Owning package: `core/ze-skills/ze_skills/types.py` (dataclasses) +
`core/ze-skills/ze_skills/migrations/versions/zsk001_skills.py` (schema). One field addition
to an existing type: `core/ze-core/ze_core/conversation/messages/types.py` (`MessageTrace`).

## Enums

### `SkillStatus` (StrEnum)

| Value | Meaning |
|---|---|
| `pending_review` | Newly imported, or reverted after a source content change; not eligible for matching (FR-004, FR-015). |
| `active` | Approved and eligible for matching/use (FR-006). |
| `disabled` | Previously active, user turned it off; retained, eligible to re-enable without re-review (FR-013). |
| `rejected` | User explicitly rejected the pending version; retained for record, never active in this form (FR-006). |

### `SkillSource` (StrEnum)

| Value | Meaning |
|---|---|
| `bundled` | Shipped inside a Ze plugin package via `ZePlugin.bundled_skill_paths()` (FR-007). |
| `imported` | Fetched from a user-submitted URL (FR-001). |

### `SkillTrigger` (StrEnum) — used only in `SkillUsageTrace`, not stored on `Skill` itself

| Value | Meaning |
|---|---|
| `automatic` | Matched via embedding relevance floor (FR-019a). |
| `explicit` | Invoked via `/skill-name` in the message (FR-019b). |

## Entities

### `Skill` (table `skills`)

| Field | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK, `gen_random_uuid()`. |
| `name` | `TEXT` | Non-empty (FR-018). Display name, not necessarily unique across sources. |
| `slug` | `TEXT` | Derived from `name` (lowercase, hyphenated); used for `/skill-name` invocation matching (FR-019b) and for distinguishing same-named skills by pairing with `source` (FR-017). |
| `description` | `TEXT` | Non-empty (FR-018); embedded for automatic matching. |
| `instructions` | `TEXT` | Full free-text instructions body from `SKILL.md` (FR-005). |
| `source` | `SkillSource` | `bundled` \| `imported`. |
| `origin_url` | `TEXT NULL` | Import URL, only set when `source = imported`. |
| `bundling_plugin` | `TEXT NULL` | Plain string plugin identifier (e.g. `"ze-calendar"`), only set when `source = bundled`. Never a core-owned enum — plugin-domain vocabulary per constitution III. |
| `status` | `SkillStatus` | See above. |
| `allowed_tools` | `JSONB NULL` | Optional list of tool-name strings from `SKILL.md` frontmatter; narrows, never expands (FR-008). |
| `has_unsupported_scripts` | `BOOLEAN` | `true` when parsing detected bundled executable scripts (FR-009); flagged in review, does not block approval of the instructions-only portion. |
| `content_hash` | `TEXT` | Hash of the currently-approved `(name, description, instructions, allowed_tools)` tuple; compared on recheck (FR-015). |
| `created_at` | `TIMESTAMPTZ` | Import/bundle-registration time. |
| `approved_at` | `TIMESTAMPTZ NULL` | Set on transition to `active`. |
| `last_checked_at` | `TIMESTAMPTZ NULL` | Updated on every recheck (scheduled or manual), regardless of whether content changed. |
| `last_check_error` | `TEXT NULL` | Set when a recheck's source became unreachable; does not deactivate the skill (spec Edge Cases — "last-approved version keeps working"). |

**Uniqueness**: `(slug, source)` unique — an imported and a bundled skill may share a slug
(distinguished by source, FR-017); two imported skills may not share a slug (re-importing the
same URL updates the existing row via the recheck/re-review path, not a duplicate).

**Validation**: `name` and `description` non-empty at parse time, before a row is ever created
(FR-018, FR-003) — enforced in `parser.py`, not just at the DB layer.

### `ReferenceFile` (table `skill_reference_files`)

| Field | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK. |
| `skill_id` | `UUID` | FK → `skills.id`, `ON DELETE CASCADE`. |
| `filename` | `TEXT` | Relative path within the imported archive. |
| `content` | `TEXT` | Stored file content (FR-022). Non-script files only — script files are never stored, only flagged via `Skill.has_unsupported_scripts`. |
| `content_type` | `TEXT` | e.g. `text/markdown`, inferred from extension. |

### `SkillReview` (table `skill_reviews`)

| Field | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK. |
| `skill_id` | `UUID` | FK → `skills.id`, `ON DELETE CASCADE`. |
| `content_snapshot` | `JSONB` | `{name, description, instructions, allowed_tools, content_hash}` as shown to the user at decision time (FR-016 — lets a later re-review compare old vs. new). |
| `decision` | `TEXT` | `approved` \| `rejected`. |
| `decided_at` | `TIMESTAMPTZ` | |

One row per approve/reject decision — including re-approval after a content-change
re-review — so prior approvals are never lost (FR-016, User Story 4).

### `SkillMatch` (not persisted — intermediate result of `SkillMatcher`, feeds `SkillUsageTrace`)

Produced per-turn by `SkillMatcher.match()` (`core/ze-skills/ze_skills/matching.py`) and consumed
by two downstream sites: `AgentContext.active_skills`/`skill_tool_names` (instruction injection +
tool narrowing) and `record_trace` (`SkillUsageTrace` construction, one `SkillMatch` → one
`SkillUsageTrace`).

```python
@dataclass
class SkillMatch:
    skill: Skill
    trigger: SkillTrigger       # "automatic" | "explicit"
    similarity: float | None = None   # set only when trigger == "automatic"
```

### `SkillUsageTrace` (not a table — a field on `MessageTrace`)

Added to `core/ze-core/ze_core/conversation/messages/types.py`:

```python
@dataclass
class SkillUsageTrace:
    skill_id: str
    name: str
    source: str          # "bundled" | "imported"
    trigger: str          # "automatic" | "explicit"
    similarity: float | None = None   # set only when trigger == "automatic"

@dataclass
class MessageTrace:
    ...  # existing fields unchanged
    skills_used: list[SkillUsageTrace] = field(default_factory=list)
```

Persisted via the existing `messages.trace` JSONB column and the existing `trace_update` WS
frame (`**asdict(trace)` already includes any new field automatically) — see research.md §9
for why this replaces a dedicated `Skill Usage` table.

## State Transitions (`Skill.status`)

```
                 import (FR-001–004)
                        │
                        ▼
                 pending_review ──reject (FR-006)──► rejected
                        │
                    approve (FR-006)
                        │
                        ▼
                      active ──disable (FR-013)──► disabled
                        │                              │
                        │◄──────enable (FR-013)────────┘
                        │
              content change detected on
              recheck (FR-015, scheduled
              or manual)
                        │
                        ▼
                 pending_review (re-review; FR-016 keeps prior
                 approved content visible for comparison)
```

`disabled → pending_review` also occurs if a content change is detected while disabled (a
recheck runs regardless of `active`/`disabled` status, since both represent "previously
approved content" that could go stale) — re-enable after a content change requires re-review
just as re-activation after edit would for an `active` skill.

`rejected` is terminal for that content version but not for the `Skill` row: a later recheck
detecting new content at the same `origin_url` moves a `rejected` skill back to
`pending_review` too (same content-change detection path), since rejection was a decision about
specific content, not a permanent block on the URL.

## Relationships

- `Skill 1 ── * ReferenceFile` (cascade delete).
- `Skill 1 ── * SkillReview` (cascade delete; full history retained even after skill removal is
  not required by the spec — `FR-014`'s "permanently remove" cascades reviews too).
- `MessageTrace.skills_used[].skill_id` references `Skill.id` informally (JSONB, not an FK —
  consistent with how `MessageTrace.tool_calls`/`memory_chunks` already reference other
  entities by ID inside the trace JSONB rather than via a relational FK).

## Config additions (`apps/ze-api/config/config.yaml`)

```yaml
skills:
  match_threshold: 0.5      # relevance floor for automatic matching (research.md §2)
  recheck:
    enabled: true
    cron: "0 6 * * *"        # daily source-content recheck (research.md §5)
```
