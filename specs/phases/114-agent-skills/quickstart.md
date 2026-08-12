# Quickstart: Agent Skills

Validates the feature end-to-end against the acceptance scenarios in
[spec.md](spec.md). Assumes `make db-up && make migrate && make dev` already running (see
root `CLAUDE.md`) and that `114-agent-skills`'s migrations (`zsk001`) have been applied.

## Prerequisites

- A `SKILL.md` reachable over HTTP for import testing. For local validation, serve one from
  the repo, e.g.:
  ```bash
  mkdir -p /tmp/test-skill && cat > /tmp/test-skill/SKILL.md <<'EOF'
  ---
  name: Pirate Speak
  description: Ends every response with "Arrr!" — use to verify skill matching end-to-end.
  ---
  Always end your response with the exact phrase "Arrr!" on its own line.
  EOF
  cd /tmp/test-skill && python3 -m http.server 8099 &
  ```

## Scenario 1 — Import and approve (User Story 1)

1. `POST /api/v0/skills/import` with `{"url": "http://localhost:8099/SKILL.md"}`.
   - **Expect**: `201`, body has `status: "pending_review"`, `name: "Pirate Speak"`, full
     `instructions` text, `has_unsupported_scripts: false`.
2. `GET /api/v0/skills/{id}` — confirm the same content is visible before approval (FR-005).
3. `POST /api/v0/skills/{id}/approve` — **expect** `200`, `status: "active"`, `approved_at` set.
4. `GET /api/v0/skills?status=active` — confirm the skill now appears.

**Validates**: FR-001–006, SC-001, SC-002.

## Scenario 2 — Reject path

1. Import a second skill from a distinct URL.
2. `POST /api/v0/skills/{id}/reject` — **expect** `200`, `status: "rejected"`.
3. `GET /api/v0/skills?status=active` — confirm it does **not** appear.

**Validates**: FR-006 (reject branch).

## Scenario 3 — Bad import

1. `POST /api/v0/skills/import` with `{"url": "http://localhost:8099/does-not-exist.md"}`.
   - **Expect**: `422`, specific error message, and `GET /api/v0/skills` shows no new row.

**Validates**: FR-003.

## Scenario 4 — Automatic matching + visible attribution (User Story 2)

1. With the "Pirate Speak" skill `active` from Scenario 1, send a chat message plausibly
   related to its description (e.g. "give me a fun greeting").
2. Inspect the assistant's response — **expect** it ends with "Arrr!".
3. Inspect the `trace_update` WS frame (or `GET /api/v0/messages/{id}/trace`) for that turn —
   **expect** `skills_used` contains one entry: `name: "Pirate Speak"`, `trigger: "automatic"`,
   `similarity` above `skills.match_threshold`.
4. Send an unrelated message (e.g. "what's 2+2") — **expect** `skills_used: []`.

**Validates**: FR-010, FR-011, FR-019a, SC-003.

## Scenario 5 — Explicit invocation (User Story 2, scenarios 4–5)

1. Send a chat message containing `/pirate-speak please summarize my day`.
   - **Expect**: response ends with "Arrr!" regardless of topical relevance; `skills_used`
     contains `trigger: "explicit"`.
2. Send a message that both names `/pirate-speak` and is independently on-topic for a second
   active skill — **expect** both entries appear in `skills_used`.

**Validates**: FR-019b, spec Edge Cases ("two or more active skills match the same message").

## Scenario 6 — Management view (User Story 3)

1. Import 3+ skills, leave them in a mix of `pending_review`/`active`/`disabled` states via
   the REST calls above (`POST .../disable` on one active skill).
2. `GET /api/v0/skills` — **expect** all skills listed with correct `source`/`status`.
3. `POST /api/v0/skills/{id}/enable` on the disabled one — **expect** `200`, back to `active`,
   no re-review required (no `SkillReview` row created by this call).

**Validates**: FR-012, FR-013, SC-005.

## Scenario 7 — Content-change re-review (User Story 4)

1. With Scenario 1's skill `active`, overwrite `/tmp/test-skill/SKILL.md` with a changed
   `instructions` body (keep name/description the same or change them — either triggers a
   hash mismatch).
2. `POST /api/v0/skills/{id}/refresh` — **expect** `200`, `status: "pending_review"`.
3. `GET /api/v0/skills/{id}` — **expect** `previous_version` present, showing the original
   approved content alongside the new content (FR-016).
4. Send a chat message that would have matched the skill — **expect** `skills_used: []` (the
   skill is inert while pending re-review, per SC-004).
5. Re-run `POST /api/v0/skills/{id}/refresh` without changing the file again — **expect** no
   status change (content unchanged branch, spec Acceptance Scenario 4.3).

**Validates**: FR-015, FR-016, SC-004.

## Scenario 8 — Unreachable source doesn't deactivate

1. Stop the local HTTP server (`kill %1`).
2. `POST /api/v0/skills/{id}/refresh` on a still-`active` skill pointing at that server.
   - **Expect**: `200` (not an error status), `status` unchanged (`active`), `last_check_error`
     populated, `last_checked_at` updated.

**Validates**: spec Edge Cases ("import source becomes permanently unreachable").

## Scenario 9 — Tool restriction narrows, never expands

1. Import and approve a skill whose frontmatter declares
   `allowed-tools: ["some_tool_the_agent_does_not_have"]`.
2. Trigger it in conversation with an agent that has neither that tool nor any others in
   common with the restriction.
   - **Expect**: the agent's available tool set for that turn is empty/unaffected beyond its
     own tools — no error, and critically no new tool becomes callable (FR-008, spec Edge
     Cases).

**Validates**: FR-008.

## Cleanup

```bash
kill %1 2>/dev/null  # stop the test SKILL.md server
```
