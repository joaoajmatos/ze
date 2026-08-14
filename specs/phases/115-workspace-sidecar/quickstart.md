# Quickstart: Workspace Environment

Validates the feature end-to-end against the acceptance scenarios in [spec.md](spec.md).
Assumes `make db-up && make migrate && make dev-full` (or Compose with the `workspace`
service healthy) and that `zws001` + `zsk002` have been applied.

Default mode after migrate is **Ask**.

## Prerequisites

- Workspace sidecar healthy: `GET $WORKSPACE_SERVICE_URL/health` → `{ "ok": true }`.
- API key as usual (`ZE_API_KEY`).

## Scenario 1 — Create a file, confirm, retrieve (User Story 1, SC-001)

1. `GET /api/v0/workspace/mode` — **expect** `"ask"`.
2. In chat, ask Ze to create `hello.txt` containing `hello workspace`.
3. **Expect** a `confirm_request` for the write; the workspace is unchanged until approve
   (`GET /api/v0/workspace/files` does not list `hello.txt` yet).
4. Approve. **Expect** the assistant reply annotated with workspace use and `hello.txt`;
   `GET /api/v0/workspace/files` lists it; `GET /api/v0/workspace/files/hello.txt` body is
   `hello workspace`.
5. Inspect `trace_update` / `GET /api/v0/messages/{id}/trace` — **expect**
   `workspace.files` includes `{path: hello.txt, op: created}` and `workspace.mode` is
   `ask`.

**Validates**: FR-001, FR-004, FR-006 Ask, FR-007, SC-001, SC-002.

## Scenario 2 — Deny does nothing

1. Ask Ze to write `denied.txt`.
2. Deny the confirmation.
3. **Expect** no `denied.txt` in the listing; the reply says the action did not run.

**Validates**: User Story 1 scenario 5.

## Scenario 3 — Auto-edit vs command (SC-008)

1. `PATCH /api/v0/workspace/mode` `{ "mode": "auto_edit" }`.
2. Ask Ze to write `auto.txt`. **Expect** no confirm; file exists.
3. Ask Ze to run `python3 -c "print(1)"`. **Expect** a confirm; nothing runs until
   approve.

**Validates**: FR-006 Auto-edit, FR-029, SC-008.

## Scenario 4 — Off and Plan

1. Mode `off`. Ask Ze to write a file. **Expect** refusal; listing unchanged.
2. Mode `plan`. Ask Ze to write `planned.txt`. **Expect** a preview, no file, no confirm
   execute.
3. Mode `auto`. Ask Ze to write `fast.txt`. **Expect** no confirm; file exists.

**Validates**: FR-006 Off / Plan / Auto.

## Scenario 5 — Mode persists across reconnect (FR-029)

1. Set mode to `auto`. Close the chat app (disconnect WS).
2. Reopen, start a new conversation. `GET /api/v0/workspace/mode` — **expect** `auto`.

## Scenario 6 — Durability across disconnect (SC-003)

1. With files present, disconnect and return later the same day.
2. **Expect** the same listing (unless a reset happened).

## Scenario 7 — Public fetch, no Ze credentials (FR-026, SC-004)

1. Mode `auto`. Ask Ze to `curl` a public URL into `public.txt`.
2. **Expect** the file exists and contents match the public resource.
3. Ask Ze to print env. **Expect** no `OPENROUTER_API_KEY` / `DATABASE_URL` /
   `WORKSPACE_API_TOKEN` in the preview shown to the user.

## Scenario 8 — Chat attach is place, not ingest (FR-027)

1. Attach `doc.txt` in the composer (REST upload, then send).
2. **Expect** `doc.txt` (or a deduped name) in the workspace listing.
3. **Expect** no new `ingested_content` row and no new memory facts from that place.

## Scenario 9 — Opt-in ingest (FR-028)

1. With `doc.txt` in the workspace, ask Ze to ingest it (or
   `POST /api/v0/workspace/files/doc.txt/ingest`).
2. **Expect** the existing ingestion pipeline to run; `doc.txt` still in the workspace.

## Scenario 10 — Skill scripts require executable approval (User Story 2, SC-005)

1. Import a skill zip that contains `scripts/write_marker.py` writing `marker.txt`.
2. `POST .../approve` (instructions only). **Expect** `has_scripts: true`,
   `executable_approved: false`.
3. Invoke the skill. **Expect** instructions may apply; `marker.txt` is **not** created;
   `skills_used[].script_ran` is false.
4. `POST .../approve-executables`. Mode `auto`. Invoke again.
5. **Expect** `marker.txt` exists; turn annotated with skill **and** script ran;
   `workspace_runs` row has `skill_script_path`.

## Scenario 11 — Workspace view: list, upload, retrieve, reset (User Story 3, SC-006)

1. Open `/workspace`. **Expect** listing with names, sizes, mtimes.
2. Upload `from-ui.bin`. **Expect** it appears; retrieve matches.
3. `POST /api/v0/workspace/reset` → confirm. **Expect** subsequent listing empty.
4. Reset without confirming. **Expect** files unchanged.

## Scenario 12 — Unavailable sidecar (SC-007, FR-010)

1. Stop the workspace service.
2. Ask Ze to write a file. **Expect** a clear unavailable warning, no fabricated file,
   other chat capabilities still work. `GET /api/v0/workspace` has `available: false`.

## Scenario 13 — Unattended Auto only (User Story 4)

1. Mode `ask`. Trigger a scheduled/workflow step that would `workspace_write`.
   **Expect** no file (commands/writes unattended are skipped).
2. Mode `auto`. Trigger again. **Expect** the file; `GET /api/v0/workspace/runs` shows
   `origin: "unattended"`.

## Scenario 14 — Busy mutex and timeout

1. Mode `auto`. Start a run that sleeps past `run_timeout_seconds`.
2. **Expect** status `timed_out`, user told it ran too long, partial files inspectable.
3. While a long run would be in flight (or simulated busy), a second run is refused or
   waits then refused with a clear busy message — never interleaved corruption.

## Cleanup

Restore mode to `ask` if you changed it: `PATCH /api/v0/workspace/mode` `{"mode":"ask"}`.
