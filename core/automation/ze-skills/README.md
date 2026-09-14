# ze-skills

Standard-compatible Agent Skills system for Ze — import, review, matching, and
tool-narrowing. Bundled scripts persist here and run in the workspace after a
second executable approval.

## Role in Ze

Skills add reusable instructions and reference knowledge to a conversation. They do
not grant new tool access beyond what an agent already has. Users import a skill
from a URL (`SKILL.md`, optionally zipped with supporting files), review the full
parsed content, and approve it before it can affect any turn. Developers can also
ship skills inside a plugin package; those land as `source=bundled` and skip the
instructions review gate.

Matching is global across every agent. A turn picks up a skill in two ways:
embedding similarity of the message against the skill's name + description, or an
explicit `/skill-name` token in the message. Matched skills prepend their
instructions to the system prompt, intersect (never union) `allowed-tools` with the
agent's own `tools` list, and show up on `MessageTrace.skills_used`.

Scripts are a separate gate. Approving instructions does not set
`executable_approved`. After that second approval, the agent may call
`workspace_run_skill_script`; the [workspace sidecar](../../docs/workspace.md)
writes the stored bytes under `/workspace` and runs them under the workspace mode table.

### Key features

- Import (`importer.py` / `parser.py`) — fetch a `SKILL.md` URL or zip, parse YAML
  frontmatter + Markdown body, store reference files and script bytes
- Review (`review.py`) — pending → active/rejected, disable/enable without a new
  review, remove (imported only), refresh that reverts to pending review when
  source content changes, `approve_skill_executables()` as a second gate
- Matching (`matching.py`) — `SkillMatcher` caches embeddings of active skills,
  cosine-compares the turn's routing embedding, and parses `/skill-name` tokens
- Bundled skills — `ZePlugin.bundled_skill_paths()` entries register at startup as
  `source=bundled`, `status=active`, idempotent on `(slug, source)`
- Recheck (`jobs/recheck.py`) — daily `SkillRecheckJob` re-fetches every imported
  skill's origin URL; unreachable sources stay active and record `last_check_error`

### Integration

`ze-api`'s container calls `build_skills_stack()` at startup, injects
`skill_matcher` into the graph's `configurable` dict, and registers bundled skills
from every loaded plugin. The `match_skills` graph node
(`ze_core.orchestration.nodes.skills`) runs after `fetch_context` and populates
`AgentContext.active_skills` / `skill_tool_names`. `GET/POST /api/v0/skills`
(`rest.py`) is the management surface for `ze-web`'s `widgets/skill-management`.
This package is wired directly by `ze-api`, not as a `ZePlugin`.

User-facing guide: [docs/skills.md](../../docs/skills.md).

## Responsibilities

| Module | What it provides |
|---|---|
| `types.py` | `Skill`, `SkillReview`, `SkillScript`, `ReferenceFile`, `SkillMatch`, `SkillStatus` / `SkillSource` / `SkillTrigger` |
| `errors.py` | `SkillParseError`, `SkillNotFoundError`, `InvalidSkillTransitionError` |
| `parser.py` | `parse_skill_md()` — YAML frontmatter + Markdown body, script-ref detection |
| `importer.py` | `fetch_skill_source()` — HTTP fetch of a `SKILL.md` URL or zip archive |
| `store.py` | `SkillStore` protocol, `PostgresSkillStore` |
| `review.py` | approve / reject / disable / enable / remove / refresh / approve executables |
| `matching.py` | `SkillMatcher` — embedding similarity + `/skill-name` invocation |
| `rest.py` | Thin dict-returning wrappers for the `/api/v0/skills` routes |
| `jobs/` | `SkillRecheckJob` — daily origin-URL content recheck |
| `bootstrap.py` | `build_skills_stack()`, `build_skill_matcher()`, `register_bundled_skills()`, `register_proactive_jobs()` |
| `migrations/` | `zsk001` — `skills`, `skill_reference_files`, `skill_reviews`; `zsk002` — `skill_scripts`, `has_scripts`, `executable_approved` |

## Dependencies

`ze-agents`, `ze-proactive`, `ze-logging`, `ze-data`.

Third-party: `httpx`, `asyncpg`. Stdlib: `zipfile`.

## Configuration

Read from `apps/ze-api/config/config.yaml`:

```yaml
skills:
  match_threshold: 0.5   # cosine floor for automatic matching
  recheck:
    enabled: true
    cron: "0 6 * * *"    # daily source-content recheck
```

## Usage

```python
from ze_skills.bootstrap import build_skills_stack, build_skill_matcher
from ze_skills.types import Skill, SkillStatus

stack = build_skills_stack(shared, settings)
matcher = build_skill_matcher(stack.skill_store, embedder, settings)
active = await stack.skill_store.list(status=SkillStatus.ACTIVE)
```

Wired by `ze-api`. Plugin authors do not import this package; they declare bundled
skills via `ZePlugin.bundled_skill_paths()`.

## Testing

From the repo root:

```bash
make test-skills
```

See [docs/testing.md](../../docs/testing.md).
