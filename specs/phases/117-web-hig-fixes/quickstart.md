# Quickstart: Validating the Web UI HIG Audit Fixes

## Prerequisites

```bash
make db-up                # Postgres, if not already running
make dev                  # backend on :8000 (AUTO_MIGRATE + dev seed data recommended)
make web                  # ze-web dev server on :5173
```

A real `OPENROUTER_API_KEY` in `apps/ze-api/.env` is required to validate
User Story 1 (a placeholder key will fail before reaching the point where
the bug reproduces). `AUTO_SEED_DEV_DATA=true` gives realistic Goals/
Workflows/Contacts data for User Story 10's humanization check — note the
known seeder bug (`memory_facts.claim_kind` NOT NULL violation, unrelated to
this feature) may require `AUTO_SEED_DEV_DATA=false` plus manually creating
a couple of workflows/goals with intentionally snake_case titles to exercise
User Story 10.

## Per-story validation

**US1 — Chat always resolves.** Open `/`, send a message, and do not touch
the page. Confirm the reply renders and the composer unlocks without a
manual reload, within normal response time. Repeat 5–10× across fresh
sessions (per SC-001) — zero should require a reload.

**US2 — Nav reachable at every width.** Resize the browser window to
~850px wide. Confirm every item under Work/Knowledge/System/Plugins is
reachable from the collapsed sidebar (not just visible as an unlabeled
icon).

**US3 — Panel always dismissible.** Open the contextual panel (floating
launcher or Cmd/Ctrl+K) from at least 3 different pages. Confirm an
on-screen close control is visible in each case, and confirm Escape closes
it in each case.

**US4 — Panel never blocks primary controls.** On a ~390px-wide viewport,
scroll the Workflows (or Goals) list to its last row. Confirm the floating
launcher does not overlap the row's primary action button.

**US5 — Panel context label always correct.** From Settings (or any
non-Chat page), open the panel via keyboard shortcut. Confirm the label
names the current page, not "Chat".

**US6 — Settings adapts to width.** Open Settings at a typical laptop
width and again at a very wide desktop width. Confirm the layout is not
confined to a narrow left-pinned column at either size.

**US7 — Icon-only nav is screen-reader accessible.** At the ~850px
collapsed-sidebar width, use a screen reader or an accessibility inspector
(e.g. the browser devtools Accessibility panel) to confirm each nav icon
announces its destination name.

**US8 — Mobile nav overflow.** With the full set of plugin-contributed
nav items enabled, view the bottom bar on a ~390px viewport. Confirm
comfortable tap targets and a clear path to any items beyond the
comfortably-fitting set.

**US9 — Message feedback + AI disclosure.** Open a conversation with at
least one assistant reply. Confirm a feedback/retry affordance appears on
hover/focus, and confirm a visible AI-disclosure caption is present near
the composer.

**US10 — Polish.** Confirm mobile nav label legibility, a comfortable tap
target on the breadcrumb back button, and humanized (not raw snake_case)
titles/statuses in Workflows/Goals lists.

## Automated checks

```bash
make test-web   # Vitest — new/updated tests per touched component
make lint        # ruff (backend, only if US1 touches ze-api) + web lint
```

No `make test-<package>` backend target changes are expected unless
research.md's Unknown 1 investigation concludes the fix is server-side, in
which case the relevant `ze-api`/`ze-core` test suite must also pass.
