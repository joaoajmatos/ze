# Feature Specification: Workspace Environment

**Feature Branch**: `115-workspace-sidecar`

**Created**: 2026-08-14

**Status**: Implemented

**Input**: User description: "Spec the workspace sidecar. Ze is a 24/7 companion with an always-on mind and thin clients (web now, desktop later). Skills are finished as instructions-only; they cannot run bundled scripts, and Ze has no computer — no files, no shell, no place to actually do work. Add a durable, isolated workspace on the always-on side (the same kind of split as the existing web-browsing helper): a sandboxed environment where agents can read/write files and run commands, and where approved skill scripts can execute. Artifacts come back to the user. The workspace must not receive Ze's credentials or reach Ze's internals. Desktop/local-machine access and GUI computer-use (screen, mouse) are out of scope. Do not move the mind into a desktop app."

## Clarifications

### Session 2026-08-14

- Q: When a command or skill script is started from a conversation, should the turn wait for it, always background it, or wait briefly then detach? → A: Destination UX is wait-then-detach (Cursor-like): short runs finish on the same turn; longer runs continue; when they finish Ze starts an automatic follow-up turn on that thread; if the client is offline, Ze also sends a push notification. Do not rewrite conversations to be generally async. Split the work: this spec is the workspace (the computer); a sibling spec is detached runs and follow-through.
- Q: What network may a workspace program use? → A: Public internet only. Ze’s private services and credentials stay unreachable.
- Q: Can the user put their own files into the workspace? → A: Yes. A chat attachment and an upload in the workspace view both land as workspace files. Landing a file does not run content ingestion; the user may later ask Ze to ingest a workspace file through the existing ingestion path.
- Q: What should require confirmation by default? → A: Claude Code-like workspace modes: Off · Plan · Ask (default: confirm commands and Ze’s file changes) · Auto-edit (file writes/edits without asking; commands/scripts still confirm) · Auto (commands and file changes without asking). Reset always asks. User-initiated place, read, and retrieve never ask.
- Q: When you set a workspace mode, how long does it last? → A: Until you change it. Survives closing the chat app and new conversations.
- Q: In Off, can the user still inspect the workspace? → A: Yes. Off blocks Ze (conversation/agent tools and unattended work). User-initiated list, read, place, and retrieve via the workspace view still work and never confirm. Reset still confirms.
- Q: May unattended work write files in Auto-edit? → A: Yes for file writes/deletes. Unattended commands and skill scripts still require Auto. Auto-edit is not permission for unattended commands.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask Ze to do real work and get files back (Priority: P1)

A user asks Ze to do something that needs a computer — write a file, transform data, run a command, produce a zip, generate a report. The user can also give Ze a file (attach it in chat) so the work can run on that file. Ze does that work in a dedicated workspace that belongs to this Ze, not on the user's laptop and not inside Ze's own private records. In this spec, that work completes inside the conversation turn: the user sees what ran and what it produced, and can take the resulting files.

Closing the chat app, putting the phone down, or disconnecting does not wipe that work. The workspace lives with Ze's always-on side, so the files are still there when the user comes back. Runs that outlive the turn, an automatic follow-up when they finish, and a push if the user is offline are the intended next spec — not this one.

**Why this priority**: Without this, skills stay as extra instructions and Ze still cannot *do* anything. This is the core product gap: a place to work.

**Independent Test**: Can be fully tested by asking Ze to create a named file with known contents, confirming the turn shows that the workspace was used and the file was created, downloading (or otherwise retrieving) that file and verifying the contents, then disconnecting the client and confirming the file is still there on return.

**Acceptance Scenarios**:

1. **Given** a connected conversation, **When** the user asks Ze to create a file with specific contents in the workspace, **Then** Ze performs that work in the workspace and the reply is annotated with the workspace use and the resulting file.
2. **Given** a file just created in the workspace, **When** the user retrieves it, **Then** the contents match what was requested.
3. **Given** files already in the workspace, **When** the user disconnects the chat app and later returns, **Then** those files are still present.
4. **Given** workspace mode is Ask, **When** Ze is about to run a command or write a file, **Then** Ze asks for confirmation first and does nothing until the user approves, denies, or edits.
5. **Given** the user denies a workspace action, **When** the turn completes, **Then** nothing was executed in the workspace and the user is told so.
6. **Given** workspace mode is Auto-edit, **When** Ze writes or edits a file, **Then** it proceeds without asking; **When** Ze is about to run a command or skill script, **Then** it still asks.
7. **Given** workspace mode is Auto, **When** Ze runs a command or writes a file, **Then** it proceeds without asking (reset still asks).
8. **Given** workspace mode is Plan, **When** the user asks Ze to do computer work, **Then** Ze shows what it would run or write and does not execute.
9. **Given** workspace mode is Off, **When** the user asks Ze to do computer work, **Then** Ze refuses and the workspace is unchanged.
10. **Given** the user set workspace mode to Auto and then closed the chat app, **When** they return in a new conversation, **Then** the mode is still Auto.
11. **Given** the workspace environment is unavailable, **When** the user asks Ze to do computer work, **Then** Ze says the workspace is unavailable and does not pretend the work happened.
12. **Given** the workspace is available, **When** a command fetches a public internet resource into a workspace file, **Then** the file is created from that public source and Ze's credentials are not used or exposed.
13. **Given** the user attaches a file in chat and asks Ze to work on it, **When** the turn completes, **Then** that file is in the workspace under a clear name and was not copied into long-term memory unless the user separately asked to remember or ingest it.

---

### User Story 2 - Approved skill scripts actually run (Priority: P1)

A user has imported a skill that includes executable scripts. In the previous skills phase those scripts were flagged as unsupported and only the instructions could take effect. Now, after the user explicitly approves that the scripts may run, Ze executes them in the workspace when that skill is used, and the user can see that a skill script ran — not only that the skill's instructions were applied.

A skill that was previously approved as instructions-only does not silently start running its scripts. The user must approve the executable portion.

**Why this priority**: This is the reason to spec the workspace immediately after skills. The open Agent Skills format includes scripts; without a computer they cannot be honored, and without a re-approval step the earlier review contract is broken.

**Independent Test**: Can be fully tested by approving a skill that includes a script which writes a distinctive file, invoking that skill, and confirming both that the script ran in the workspace (file exists, turn is annotated) and that a previously instructions-only approval did not run scripts until a fresh executable approval.

**Acceptance Scenarios**:

1. **Given** an active skill whose scripts the user has approved to run, **When** that skill is used in a conversation, **Then** Ze may execute the skill's bundled scripts in the workspace and the turn is annotated with both the skill and that a script ran.
2. **Given** a skill that was approved earlier as instructions-only (scripts flagged unsupported), **When** the user has not separately approved the executable portion, **Then** Ze still applies the instructions but MUST NOT run the scripts.
3. **Given** a pending skill that includes scripts, **When** the user reviews it, **Then** the review plainly shows that scripts will be able to run in the workspace if approved, distinct from instructions-only approval.
4. **Given** a skill script that fails (missing tool, non-zero result, timeout), **When** the skill is used, **Then** the user is told the script failed and why, in plain language, and partial workspace changes that did occur remain inspectable.
5. **Given** a skill that has been disabled or reverted to pending review, **When** a conversation would have used it, **Then** none of that skill's scripts run.

---

### User Story 3 - Inspect, retrieve, and reset the workspace (Priority: P2)

The user wants to see what is in Ze's workspace, put files into it, retrieve files from it, and wipe it when they want a clean slate. The workspace is not a black box. Reset is deliberate and confirmed.

**Why this priority**: Trust in an environment that can run commands depends on being able to look inside it and empty it. The P1 stories still deliver value if the user only sees files attached to a turn; this story makes the environment operable over time.

**Independent Test**: Can be fully tested by creating files via a conversation, opening a workspace view, uploading a named file, retrieving it, confirming reset, and confirming a subsequent listing is empty.

**Acceptance Scenarios**:

1. **Given** files in the workspace, **When** the user opens the workspace view, **Then** they see a listing of what is there (names, sizes, when last changed).
2. **Given** a file in the listing, **When** the user retrieves it, **Then** they receive that file's contents.
3. **Given** the user asks to reset the workspace, **When** they confirm, **Then** all files are removed and a subsequent listing is empty.
4. **Given** a reset is requested, **When** the user has not confirmed, **Then** the workspace is unchanged.
5. **Given** a command is currently running, **When** the user requests a reset, **Then** Ze either waits until the run finishes or stops the run and then resets — it never leaves a run writing into an emptied workspace without telling the user.
6. **Given** the workspace view, **When** the user uploads a file, **Then** that file appears in the listing with the expected name and size, and it is not copied into long-term memory unless the user separately asked to remember or ingest it.

---

### User Story 4 - Background work may use the same workspace (Priority: P3)

When workspace mode is Auto, scheduled or otherwise unattended work (for example a workflow step) may use the same workspace even if no chat app is open. In every other mode, unattended work must not run commands; it skips or waits rather than acting in secret. Auto-edit is not enough for unattended command execution.

**Why this priority**: This is the 24/7 property applied to hands, not only to the mind. It is secondary to being able to do work in a live conversation.

**Independent Test**: Can be fully tested by setting workspace mode to Auto, triggering a scheduled step that writes a known file while the chat app is disconnected, and confirming the file is present afterward; then repeating in Ask mode and confirming no file was written.

**Acceptance Scenarios**:

1. **Given** workspace mode is Auto, **When** unattended work that needs the workspace runs, **Then** it uses the same durable workspace and the result is later visible to the user.
2. **Given** workspace mode is not Auto, **When** unattended work would need the workspace, **Then** it does not execute commands there.
3. **Given** unattended work used the workspace, **When** the user later inspects recent activity, **Then** they can see that the workspace was used, by what, and what it produced.

---

### Edge Cases

- What happens when a command or script exceeds its time budget? It is stopped. The user is told it ran too long. Any files it already wrote remain inspectable.
- What happens when output is very large? The user sees a truncated preview and can retrieve the full output as a workspace file rather than a wall of text in chat.
- What happens when the workspace is full? Ze refuses new writes, tells the user it is full, and points them at reset or deleting files.
- What happens when two commands would run at once? They do not silently interleave in a way that corrupts each other's work. One waits, or the second is refused with a clear message, until the first finishes.
- What happens if a command or script tries to read Ze's credentials, reach Ze's private services, or write outside the workspace? It fails. Those resources are not available in the workspace. The user is not shown secrets in the error. Public internet access is allowed; a failed public fetch is reported as a failed run, not as a secret or an internal outage.
- What happens if the workspace becomes unreachable mid-run? The turn reports failure. Ze does not invent a successful result. Existing files are unchanged as far as Ze can tell.
- What happens with binary files? They can be stored and retrieved. Chat shows a file chip, not a dump of binary data.
- What happens if a skill script tries to run a tool Ze has not made available in the workspace? The script fails with a clear "not available" outcome; Ze does not install new system-wide software to satisfy it in this phase.
- How does the system handle a path that attempts to escape the workspace (parent directories, absolute paths outside it)? Treated as outside the workspace and refused.
- What happens when the user places a file whose name already exists in the workspace? Ze does not overwrite the existing file. It stores the new file under a distinct name and tells the user both names.
- What happens when a placed file would exceed the storage ceiling? The place is refused, the workspace is unchanged, and the user is told it is full.
- What happens when the user edits a confirmation (changes the command or the file to write)? Ze runs the edited version, not the original.
- What happens if mode is Plan or Off and a skill with executable approval is used? Instructions may still apply; scripts do not run. Plan shows what would have run.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a single durable workspace for this Ze that persists across conversations and across the chat app being closed, until the user resets it.
- **FR-002**: System MUST keep the workspace in an isolated environment on Ze's always-on side, separate from Ze's private records and from the user's personal computer.
- **FR-003**: System MUST NOT place Ze's credentials, private keys, or internal service locations into the workspace, and MUST prevent workspace programs from reaching Ze's private services.
- **FR-026**: Workspace programs MUST be able to use the public internet. They MUST still be unable to reach Ze's private services or see Ze's credentials (FR-003). A program that needs the network and cannot reach a public destination fails clearly; Ze does not pretend the fetch succeeded.
- **FR-004**: Users MUST be able to have Ze create, read, update, list, and delete files inside the workspace through conversation.
- **FR-005**: Users MUST be able to have Ze run command-line programs and scripts inside the workspace through conversation, and MUST see the outcome (success, failure, output preview) on that turn.
- **FR-006**: System MUST provide these workspace execution modes, default **Ask**:
  - **Off** — Ze does not act in the workspace (conversation/agent tools refuse; unattended work does not run). The workspace is unchanged by Ze. User-initiated list, read, place, and retrieve via the workspace view still work.
  - **Plan** — show what would be run or written; do not execute.
  - **Ask** — confirm commands/scripts and file changes Ze makes, then act only after approve / deny / edit.
  - **Auto-edit** — file writes and edits proceed without asking; commands and skill scripts still confirm.
  - **Auto** — commands, skill scripts, and file changes proceed without asking.
  Reset always requires confirmation in every mode. User-initiated place, read, list, and retrieve never require confirmation.
- **FR-007**: System MUST visibly annotate any conversational turn that used the workspace, including whether a skill script ran, in the same spirit as skill-used attribution.
- **FR-008**: System MUST record, for each workspace run, enough explainability that the user can later see what ran, who started it (conversation vs unattended work), which skill if any, whether it succeeded, and which files it touched.
- **FR-009**: System MUST stop a run that exceeds a configured time budget and MUST cap how much output is inlined into a chat reply, offering the rest as a retrievable file.
- **FR-010**: System MUST degrade clearly when the workspace is unavailable: warn, refuse the work, never fabricate a result. Other Ze capabilities continue.
- **FR-011**: System MUST allow an approved skill's bundled scripts to execute in the workspace when the user has approved that executable portion.
- **FR-012**: System MUST NOT run scripts for a skill that was approved only as instructions, even if the workspace now exists; a separate executable approval is required.
- **FR-013**: System MUST show, during skill review, that approving scripts means they can run in the workspace, distinct from approving instructions.
- **FR-014**: Users MUST be able to list workspace files, retrieve a file, place a file into the workspace from the workspace view, and reset the workspace to empty after confirmation.
- **FR-015**: System MUST refuse attempts to read or write outside the workspace boundary.
- **FR-016**: System MUST make a shell and ordinary scripting runtimes available in the workspace. Adding new system-wide software to satisfy a skill is out of scope; missing tools fail clearly.
- **FR-017**: System MUST NOT grant a skill any workspace capability beyond what Ze's agents already have in this environment. A skill may narrow what it uses; it may not expand the workspace's reach.
- **FR-018**: When workspace mode is Auto, unattended work MAY use the same workspace. Unattended commands and skill scripts MUST run only when mode is Auto. Unattended file writes and deletes MAY run when mode is Auto-edit or Auto. In every other mode, unattended work MUST NOT execute commands there. Auto-edit MUST NOT be treated as permission for unattended commands.
- **FR-019**: System MUST keep workspace runs from silently interleaving: a second run waits or is refused until the first finishes.
- **FR-020**: System MUST enforce a storage ceiling on the workspace and tell the user when writes are refused because it is full.
- **FR-021**: Files in the workspace (created by Ze, fetched, or placed by the user) MUST remain in the workspace until the user retrieves them, deletes them, or resets. Ze MUST NOT automatically copy them into long-term memory or run content ingestion on them.
- **FR-022**: The existing web-browsing helper remains a separate capability. This phase MUST NOT fold browsing the public web into the workspace, and MUST NOT add GUI computer-use (seeing a screen, moving a pointer, typing into arbitrary apps).
- **FR-023**: This phase MUST NOT move Ze's always-on mind into a desktop app, and MUST NOT give the workspace access to the user's personal computer files or applications.
- **FR-024**: Conversational workspace runs in this spec MUST complete inside the turn: wait until the command or script finishes, or until the time budget stops it. This spec MUST NOT detach a run from the turn, MUST NOT start an automatic follow-up turn when a run finishes, and MUST NOT send a completion push. Those belong to a sibling spec (detached runs and follow-through).
- **FR-025**: System MUST persist each workspace run as a durable record (FR-008) that a later spec can attach to — including a stable identity, the conversation it started from, status, and files touched — without changing the workspace boundary or isolation rules.
- **FR-027**: Users MUST be able to place a file into the workspace by attaching it in a conversation and by uploading it in the workspace view. Placing a file is putting bytes in the workspace, not ingesting knowledge.
- **FR-028**: Users MUST be able to ask Ze to run the existing content-ingestion path on a specific workspace file. That request is opt-in and distinct from placing or producing the file.
- **FR-029**: Users MUST be able to see the current workspace mode and switch it. The current mode MUST be visible when Ze is about to do workspace work. The chosen mode MUST persist until the user changes it, including across conversations and after the chat app is closed. A new conversation MUST NOT reset the mode to Ask.
- **FR-030**: Skill-script execution follows the same mode rules as commands (FR-006). Executable approval of a skill (FR-011) is necessary but not sufficient: Off and Plan still do not run scripts; Ask and Auto-edit still confirm each script run; Auto may run without asking.

### Key Entities *(include if feature involves data)*

- **Workspace**: The one durable, isolated working environment that belongs to this Ze. Attributes: whether it is available, how full it is, when it was last used, when it was last reset.
- **Workspace run**: One execution of a command or skill script. Attributes: stable identity, when it started and ended, what was asked to run, who started it (a conversation turn or unattended work), which conversation it belongs to, which skill if any, status (succeeded, failed, timed out, cancelled, refused), output preview, files touched. This spec completes runs inside the turn; the record must still be attachable by a later follow-through spec.
- **Workspace file**: A file stored in the workspace. Attributes: name/path inside the workspace, size, last changed time. Retrievable by the user; not automatically a memory fact.
- **Executable approval**: The user's decision that a given version of a skill's scripts may run in the workspace, distinct from approving that skill's instructions.
- **Workspace mode**: The current execution mode (Off, Plan, Ask, Auto-edit, Auto). Default Ask until the user first changes it. Then it lasts until they change it again. Governs confirmation for this spec; unattended command execution requires Auto.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from asking Ze to create a simple named file to retrieving that file with the expected contents in under 2 minutes, including any confirmation step.
- **SC-002**: 100% of conversational turns that ran a command, wrote a file, or executed a skill script carry a visible, correct workspace annotation; users can identify that the workspace was used without asking.
- **SC-003**: After disconnecting the chat app and returning later the same day, 100% of files that were in the workspace before disconnect are still there (unless the user reset in between).
- **SC-004**: 0 instances of Ze credentials or internal service locations being present in the workspace or in workspace command output shown to the user.
- **SC-005**: 100% of skills whose scripts were previously approved only as instructions remain non-executing until the user gives a separate executable approval; zero silent promotions.
- **SC-006**: A user can find a file they know is in the workspace and retrieve it, or reset the workspace to empty, in under 30 seconds from the workspace view.
- **SC-007**: When the workspace is unavailable, 100% of attempted workspace actions fail with a clear explanation and no fabricated success.
- **SC-008**: After switching from Ask to Auto-edit, a subsequent file write Ze initiates completes without a confirmation prompt, while a subsequent command still prompts, in under 30 seconds from the mode switch.

## Assumptions

- Ze remains a single-user personal assistant; there is one workspace, not a workspace per skill, per conversation, or per person.
- The workspace is a command-line environment (files, programs, scripts), not a graphical desktop. GUI computer-use is a later, separate decision.
- Access to the user's own laptop, phone files, or local apps is out of scope. A future desktop client may offer a gated local connector; it is not this phase.
- The always-on mind stays where it is. This phase adds hands beside it, the same kind of split already used for browsing the web. It does not relocate Ze into a menu-bar app.
- Confirmation uses named workspace modes (FR-006) on Ze's existing permission machinery. This phase does not invent a parallel auth system. Auto-edit is the extra mode beyond Off / Plan / Ask / Auto. The first-run default is Ask; after the user switches, the mode persists until they switch again (FR-029).
- Skills continue to apply globally across agents. Script execution uses the same matching and explicit-invocation rules as instructions; this phase only adds the ability to run the executable portion after approval.
- Bundled skill scripts are the scripts shipped with an approved skill. Ze does not, in this phase, download and run arbitrary new code from the internet as a side effect of a script unless workspace mode is Auto.
- Ordinary scripting runtimes means whatever is typically needed to run scripts in the open Agent Skills format (a shell plus common scripting languages). Exact runtime inventory is a plan-time choice; the requirement is that missing tools fail clearly rather than Ze silently installing system-wide software.
- Time budget and storage ceiling have conservative defaults suitable for a personal assistant (minutes, not hours; a bounded disk, not unlimited). Exact numbers are plan-time configuration.
- Artifact ingestion into memory is opt-in via conversation ("remember this file" / "ingest this"), not automatic. Placing a file in the workspace does not hook ingestion. Ingestion of a workspace file reuses the existing content-ingestion path; this spec does not build a second pipeline.
- The web-browsing helper stays as it is. Workspace programs may use the public internet; they cannot see Ze's credentials or private services (FR-003, FR-026). This is not a browsing session and does not replace the web-browsing helper.
- Phase 114's instructions-only skill system stays in place. This phase lifts the "scripts unsupported" limitation only for skills that receive executable approval.
- Destination UX (wait-then-detach, automatic follow-up turn on the same thread, push if the client is offline) is accepted and will be specified separately. This spec does not implement it. This spec does not rewrite conversations to be generally async; follow-through reuses starting a turn and notifying, the same way other background work already talks to the user.
- Spec split: (1) [115 Workspace Environment](../115-workspace-sidecar/spec.md) — the workspace as an isolated computer; (2) [116 Workspace Follow-Through](../116-workspace-follow-through/spec.md) — detached runs and follow-through (wait threshold, detach, cancel, one-run busy rule, automatic follow-up turn, offline push). Unattended use of the workspace (User Story 4) stays in 115 as a permission rule, not as detach/follow-through.
