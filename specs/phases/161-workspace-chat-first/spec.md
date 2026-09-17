# Feature Specification: Workspace Chat-First

**Feature Branch**: `161-workspace-chat-first`

**Created**: 2026-09-17

**Status**: Implemented

**Input**: User description: "Rework workspace so it is not a second product. Interact with the workspace in chat. The workspace screen is only a high-level view (directories and facts about the workspace). Drop execution modes. Runs belong in chat. Chat and unattended work always have access to the same computer."

**Governed by**: [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md), constitution Principle VIII, Phase 115 [`115-workspace-sidecar`](../115-workspace-sidecar/spec.md), Phase 116 [`116-workspace-follow-through`](../116-workspace-follow-through/spec.md), Phase 129 [`129-workspace-run-journal`](../129-workspace-run-journal/spec.md), Phase 131 [`131-workspace-live-output`](../131-workspace-live-output/spec.md).

**Depends on**: The durable isolated workspace already shipped (sidecar, files, commands, skill-script executable approval, wait-then-detach, run journal, live output in conversation).

**Does not start**: A second workspace; GUI computer-use; access to the user's personal computer; folding the public web-browsing helper into the workspace; changing skill executable approval; changing isolation or credential rules; relocating Ze's mind into a desktop app.

---

## Overview

Phase 115 treated the workspace as a computer **and** as a mode switcher (Off / Plan / Ask / Auto-edit / Auto). The System workspace screen then duplicated control: change mode, upload, reset, watch runs. Chat already had the real hands.

This phase hard-cuts that split. **Conversation is how you use the computer.** The workspace screen is a **map**: the tree and occupancy facts. There is no stored execution mode. Chat and unattended work (goals, workflows, jobs) always have access to the same workspace. Runs and their output live in the thread, not on the map.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Do computer work in chat (Priority: P1)

The user asks Ze to write a file, run a command, or work on an attached file. Ze uses the workspace. There is no Off or Plan switch to flip first. If the action needs a confirmation (a write, a command, a reset), that confirmation happens in the conversation, then the work proceeds. The reply shows that the workspace was used and what it produced.

**Why this priority**: This is the product: the computer is in the chat, not behind a mode and a System page.

**Independent Test**: With no mode UI present, ask Ze to create a named file, confirm if asked, and retrieve the contents through the conversation. Repeat a command. Both succeed without visiting the workspace screen.

**Acceptance Scenarios**:

1. **Given** a connected conversation and a working workspace, **When** the user asks Ze to create a file with specific contents, **Then** Ze performs that work in the workspace and the reply is annotated with the workspace use and the resulting file.
2. **Given** Ze is about to write a file or run a command in a conversation, **When** that action needs confirmation, **Then** Ze asks in that conversation and does nothing until the user approves, denies, or edits.
3. **Given** the user denies a workspace action, **When** the turn completes, **Then** nothing was executed for that action and the user is told so.
4. **Given** the user attaches a file in chat and asks Ze to work on it, **When** the turn completes, **Then** that file is in the workspace under a clear name and was not copied into long-term memory unless the user separately asked to remember or ingest it.
5. **Given** there is no workspace execution mode, **When** the user asks Ze to do computer work, **Then** Ze does not refuse because a mode is Off or Plan, and does not ask the user to switch a mode.

---

### User Story 2 - Unattended work uses the same computer (Priority: P1)

A goal, workflow, or other unattended step that needs files or a command uses the same durable workspace even if the chat app is closed. Access is always on: there is no Auto-only gate. When a run belongs to a conversation (including follow-through after detach), the user sees it in that thread. The user is not sent to the workspace screen to watch it.

**Why this priority**: Dropping modes without this pin would either lock the night shift out or leave the old Auto switch as a ghost. The user pinned always-on access.

**Independent Test**: Trigger unattended work that writes a known file while the chat app is disconnected. The file is present afterward. The same work is not blocked for lack of an Auto mode.

**Acceptance Scenarios**:

1. **Given** unattended work that needs to write a file or run a command, **When** that work runs, **Then** it uses the same workspace as conversation and is not refused for lack of a stored mode.
2. **Given** unattended work used the workspace, **When** the user later inspects recent activity in conversation (or the follow-through turn), **Then** they can see that the workspace was used, by what, and what it produced.
3. **Given** a detached conversational run, **When** it finishes, **Then** follow-through still happens on the thread (existing 116 behavior); the workspace screen is not required to learn the outcome.

---

### User Story 3 - The workspace screen is only a map (Priority: P1)

The user opens the workspace screen to see what is there: directories and files, sizes, when last changed, whether the environment is available, how full it is, whether it is busy. They do not switch a mode, upload, reset, start or stop a run, or watch command output there. To change anything, they go to chat.

**Why this priority**: Without this, the screen stays a second console and the chat-first story is a lie.

**Independent Test**: After creating files via chat, open the workspace screen and confirm a listing (names, sizes, last changed) plus occupancy facts. Confirm there is no mode control, no upload, no reset, no run list, and no live command preview. Reset and retrieve by asking in chat.

**Acceptance Scenarios**:

1. **Given** files in the workspace, **When** the user opens the workspace screen, **Then** they see a listing of what is there (names, sizes, when last changed) and facts about the environment (available or not, how full, busy or not).
2. **Given** the workspace screen, **When** the user looks for a way to change execution policy, upload a file, reset, or watch a run, **Then** those controls are absent.
3. **Given** the user wants a file's contents or a clean slate, **When** they ask in conversation, **Then** they can retrieve (or be given) the file, or reset after confirmation in that conversation.
4. **Given** a command is running, **When** the user is in the conversation that owns it, **Then** they see output and can stop it there; the workspace screen does not show that run.

---

### User Story 4 - Modes are gone (Priority: P2)

The product no longer has Off, Plan, Ask, Auto-edit, or Auto as workspace policy. Living documentation and the workspace screen do not describe or offer them. Skill executable approval still exists and is unchanged: instructions-only approval still does not run scripts.

**Why this priority**: A hidden mode field would keep the old product. Hard-cut is the point.

**Independent Test**: Grep of living product copy and the workspace screen finds no current-mode switcher and no claim that those five modes govern the workspace. Chat still works (Story 1). Unattended still works (Story 2).

**Acceptance Scenarios**:

1. **Given** a user who previously had a stored mode, **When** this phase ships, **Then** that stored policy has no effect; access follows this spec.
2. **Given** living docs (constitution index, agent guides, workspace user-facing copy), **When** they describe how the workspace is governed, **Then** they do not present Off / Plan / Ask / Auto-edit / Auto as the current product.
3. **Given** a skill approved only as instructions, **When** it is used, **Then** scripts still do not run until executable approval (115 unchanged).

---

## Edge Cases

- What happens when the workspace is unavailable? Ze says so in the conversation (or the unattended step fails clearly). The map shows unavailable. Nothing is invented.
- What happens when two commands would run at once? Same as 115: they do not silently interleave; the second waits or is refused until the first finishes.
- What happens if the user asks in chat to only plan, not execute? Ze can describe a plan in language. There is no Plan mode that globally blocks execution.
- What happens if the user asks Ze not to touch the workspace? That is a conversational request for that turn, not a stored Off mode.
- What happens on reset while a command is running? Same as 115: wait or stop the run, then reset; never leave a run writing into an emptied workspace without telling the user. Confirmation stays in conversation.
- What happens to historical phase specs that describe modes? They MAY stay as written. Living docs MUST NOT.
- What happens to follow-through, cancel, and live output already specified for conversation? They stay. They MUST NOT be re-homed onto the workspace screen.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to create, read, update, list, delete, run commands, run approved skill scripts, place files (including chat attachments), retrieve files, ingest a chosen workspace file, and reset the workspace through conversation.
- **FR-002**: The system MUST NOT provide workspace execution modes (Off, Plan, Ask, Auto-edit, Auto) as product policy. There MUST be no mode switcher and no stored mode that changes whether conversation or unattended work may use the workspace.
- **FR-003**: Conversation MUST always be allowed to use the workspace when the environment is available (subject to FR-006 confirmations, isolation rules, busy/full/unavailable failures, and skill executable approval).
- **FR-004**: Unattended work MUST always be allowed to use the same workspace when the environment is available (subject to isolation rules, busy/full/unavailable failures, and skill executable approval). It MUST NOT be gated on a former Auto or Auto-edit mode.
- **FR-005**: The workspace screen MUST show only the file/directory tree (names, sizes, last changed) and workspace facts (available or not, storage used and ceiling, busy or not).
- **FR-006**: Reset MUST always require confirmation in conversation. Writes and commands initiated from conversation MUST use the existing conversation confirmation path (approve / deny / edit) before executing. Unattended work MUST NOT pause for a confirmation the user cannot give in that moment.
- **FR-007**: The workspace screen MUST NOT offer mode changes, file upload, reset, run listing, live command output, or stop-run controls.
- **FR-008**: Workspace runs and their output MUST appear in conversation (the originating thread and any follow-through turn), not on the workspace screen.
- **FR-009**: This phase MUST hard-cut the mode product: no compatibility shim, dual-write of old and new policy, or wrap-then-replace that leaves modes working "for a while."
- **FR-010**: Isolation, public-internet-only network, credential exclusion, storage ceiling, one-run busy rule, wait-then-detach, run journal, skill executable approval, and "place is not ingest" remain as specified in 115/116/129/131. This phase MUST NOT reopen those decisions.
- **FR-011**: User-facing living documentation MUST describe chat as the way to use the workspace and the workspace screen as a map, not as a console with modes.
- **FR-012**: When the workspace is unavailable, attempted workspace actions MUST fail with a clear explanation and MUST NOT fabricate success.

### Key Entities

- **Workspace**: The one durable, isolated working environment. Attributes: available or not, how full, busy or not, last used, last reset. No execution-mode attribute in the product.
- **Workspace run**: One command or skill-script execution. Attributes unchanged in purpose from 115/129: identity, origin (conversation vs unattended), thread when conversational, status, output, files touched. Presented in conversation.
- **Workspace file**: A path inside the workspace with size and last changed time. Listed on the map; acted on in chat.
- **Executable approval**: Unchanged from 115 — scripts run only after that approval, independent of the removed modes.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user who never opens the workspace screen can go from asking Ze to create a named file to having that file (and seeing that the workspace was used) in under 2 minutes, including any confirmation in chat.
- **SC-002**: After this phase, 0 user-facing controls exist for Off / Plan / Ask / Auto-edit / Auto.
- **SC-003**: 100% of workspace runs started after this phase are inspectable from conversation (live or follow-through); 0 require the workspace screen to see output.
- **SC-004**: Unattended work that needs the workspace succeeds without any stored mode being Auto, in the same environment the map lists.
- **SC-005**: A user can open the workspace screen and, in under 30 seconds, tell what is there and how full it is, without being offered a way to run or reset from that screen.
- **SC-006**: 100% of skills still instruction-only do not run scripts; executable approval is unchanged.

---

## Assumptions

- "Always access" means the computer is never turned off by a mode. It does not mean unattended work skips isolation, ceilings, or the one-run busy rule.
- Conversation confirmations for writes and commands stay because chat is present to answer them. Unattended work proceeds without that pause because nobody is in a turn to approve. Reset stays confirm-always, in chat.
- Retrieve and reset move fully to conversation. Chat attachment remains the way to put a user file into the workspace. The map does not grow a download button as a consolation console.
- Historical specs 115/116/129/131 may keep mode language. Living guides and the shipped UI must not.
- Pre-v1: delete the mode product rather than map five modes onto hidden defaults.

## Verbatim Constraints

- `/workspace` — workspace screen route; remains the map, not a console.
