# Research: Constraint Veto on Gated Writes

**Feature**: `144-constraint-veto-mail-calendar`  
**Date**: 2026-09-16

## 1. Where the check runs

**Decision:** Evaluate in `BaseAgent.call_tool` via a `HarnessHook` (`on_tool_start`) registered at container bootstrap, not in each plugin tool body and not in `ze_core` graph nodes.

**Rationale:** Every agentic and direct `call_tool` already runs hooks. A per-tool `if send_email` list in messenger is the dual door this spec forbids. Graph-only checks miss GoalExecutor / specialist loops. Principle III: matching uses string channel/kind from the plugin, not a core enum of mail/calendar names.

**Alternatives considered:**
- Copy-paste checks in `send_email` / calendar tools — catalog tax.
- `capability_check` graph node — wrong layer; tools can run without that node.
- Gate every `ToolAccess.WRITE` — would veto `remember_fact`.

## 2. How a write opts in

**Decision:** Extend `@tool` / `ToolSpec` with `constraint_gate: bool = False` (verbatim). Optional `constraint_describe` callable `(args: dict) -> ConstraintWriteView`. Default describe: kind=`tool_name`, empty parties/time, summary from args.

**Rationale:** One mark on the write. New plugins set the flag. No `ZePlugin.constraint_gated_tools()` list that can drift from the decorator.

**Alternatives considered:**
- Plugin hook returning name lists — two sources of truth.
- Core frozenset of tool names — forbidden by the spec pin.

## 3. Write description and matching

**Decision:** `ConstraintWriteView` fields: `tool_name`, `kind` (plugin string: `outbound_message`, `calendar_mutation`, `reminder_write`, …), `channel` (plugin string or none), `parties` (names/addresses), `when` (aware datetime or none), `summary`. Matcher loads reviewed, non-contradicted `constraint` family facts. Conservative: time window vs `when` in user timezone; channel tokens (email/mail vs calendar vs reminder); party substrings of length ≥ 3. If any fact clearly applies → refuse or confirm. If a fact might apply → confirm. Email-only facts do not auto-hit calendar.

**Rationale:** Spec FR-009. No new NLI product this phase.

**Alternatives considered:**
- NLI entailment per write — later if too deaf.
- LLM judge of applicability — can lie; not a hard gate.

## 4. Refuse vs confirm

**Decision:** Reuse existing confirmation interrupt (`GateDecision.AWAIT_CONFIRMATION` / pending confirmation), not new UI. Clear violations (named party + matching channel, or time window clearly containing `when`) refuse without sending. Ambiguous → confirm. HookAbort with a structured tool result `{ok: false, veto: true, constraint_ids: [...], error: "..."}` so 143-style `ok` is consistent. For confirm, hold the write (do not execute the tool) until approve.

**Rationale:** Spec reuses approve/deny. Principle VIII: do not execute then undo.

## 5. First adopters

**Decision:**
- `send_email` — `constraint_gate=True` (not `draft_email` except person-level never-contact when draft names them — mark `draft_email` gated with kind that time-windows ignore).
- `create_event`, `update_event`, `delete_event`.
- `set_reminder`, `cancel_reminder`.
- Prospecting has no SMTP send; outreach send is `send_email`. Do not gate `add_prospect`. Treat `draft_outreach` like `draft_email` (person-level never-contact). Add a test that a prospecting-driven `send_email` still hits the hook.

**Rationale:** Honest to the codebase. FR-008’s “prospecting outreach” is satisfied by the shared `send_email` gate plus draft person-check.

## 6. Earned veto claims

**Decision:** Structured `veto: true` on the tool result is the earned signal. Extend companion `enforce_memory_confirmations` (or a sibling `enforce_constraint_confirmations` in the same honesty module, re-exported if specialists need it) so “I won’t send/schedule because of your constraint” is stripped unless a gated tool returned `veto` true this turn. Messenger/calendar/reminders `run` must apply the same function (or call the shared helper) and buffer `token_sink` like companion. Do not put the dialect in `ze-agents`.

**Rationale:** Same honesty class as 143; dialect stays in plugins. Specialists that can speak the line must not skip the gate.

**Alternatives considered:**
- Prompt-only “don’t claim veto” — already failed for remember.
- Core BaseAgent strip — Principle III companion/mail dialect in contracts.

## 7. Reviewed facts source

**Decision:** Hook reads via existing memory store: `contradicted = false AND reviewed = true` and predicate family `constraint` (predicate `constraint` or family metadata already used by admission). No new table.

**Rationale:** Phase 141 reviewed-always-on is the same set.
