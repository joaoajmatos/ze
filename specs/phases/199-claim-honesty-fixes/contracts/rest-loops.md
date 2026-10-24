# Contract: `GET /api/v0/loops` (`listLoops`)

Only one field changes, on `LoopListItem`:

| Field | Before | After |
|---|---|---|
| `claim_kind` | `string` (stored at creation; `suspicion` stayed after confirm or promote) | `string \| null`. Derived from `state`: `suspicion` for suspected, `priority` for active, drifting and closed, `null` for dropped. |

There is no path, parameter or operation-id change. `@myguyze/ze-client` is regenerated with `make codegen`, and `LoopListItem.claim_kind` becomes `string | null`.

Web readers that must accept `null`: `apps/ze-web/src/pages/world/lib/concerns.ts`, `apps/ze-web/src/widgets/loops-rail/ui/LoopsRail.tsx`, `apps/ze-web/src/pages/doing-goal/ui/DoingGoalPage.tsx`.
