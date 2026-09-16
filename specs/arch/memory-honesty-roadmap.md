# Memory honesty roadmap

> **Status:** Living note. Phase 144 (`specs/phases/144-constraint-veto-mail-calendar/`) is the constraint write-gate. Do not start 145 (unsolicited recitation) in the 144 tree.
> **Date:** 2026-09-16
> **Related:** [Pre-v1 Hard Cuts](pre-v1-hard-cuts.md), [Ze Doctrine](ze-doctrine.md), Phases [140](../phases/140-memory-admission/spec.md)–[143](../phases/143-memory-claim-honesty/spec.md)
> **Date:** 2026-09-16
> **Related:** [Pre-v1 Hard Cuts](pre-v1-hard-cuts.md), [Ze Doctrine](ze-doctrine.md), Phases [140](../phases/140-memory-admission/spec.md)–[143](../phases/143-memory-claim-honesty/spec.md)

---

## Context

Phases 140–142 added remember/forget tools, prompt constitution, and speech-act routing. Phase 143 gates “I’ll remember / I forgot” on the companion turn path (`ok` true from `remember_fact` / `forget_fact`) and replaces loose forget matching with a precision ladder. Everything below waits until that gate exists, so later work does not police a lie that 143 should already block.

---

## After Phase 143 (ordered)

### 144 — Constraint veto on gated writes (P5) — M — shipped

Standing constraint facts (never email after 22:00) store as biography and now block or confirm writes plugins mark `constraint_gate`. One harness hook, not a core mail/calendar name list. First adopters: mail send, calendar mutations, reminders; prospecting send is `send_email`.

Spec: [`specs/phases/144-constraint-veto-mail-calendar/`](../phases/144-constraint-veto-mail-calendar/spec.md).

### 145 — Response-level unsolicited recitation — S — shipped

141 forbids “I remember that you…” in the **prompt**. The reply can still recite biography unsolicited. Same turn-path idea as 143, after confirmations are gated, so the filter is not confused with remember/forget success language. Size S: extend the companion reply gate (or shared constitution enforcement) to unsolicited recitation; `TurnSurfacing` still owns open items.

Spec: [`specs/phases/145-unsolicited-recitation/`](../phases/145-unsolicited-recitation/spec.md).

### 146 — Forget vs cancel across stores (R14) — M — shipped

Users say “forget the dentist” meaning a reminder, loop, or goal. `forget_fact` is biography-only. Cancel speech routes to reminder/loop/goal tools; nested delegate `tool_calls` earn domain confirmations, not forgotten-fact claims.

Spec: [`specs/phases/146-forget-vs-cancel/`](../phases/146-forget-vs-cancel/spec.md).

Do not start 147 (ingest vs remember) in the 146 tree.

### 147 — Ingest vs remember honesty (R7) — S — shipped

Ingest still writes synthesized perception facts via `MemorySink`. The model must not talk as if `remember_fact` ran on a PDF. Copy and eval treat ingest as ingest.

Spec: [`specs/phases/147-ingest-remember-honesty/`](../phases/147-ingest-remember-honesty/spec.md).

Do not start 148 (extractor dual-write) in the 147 tree.

### 148 — Extractor dual-write, then hard speech-act classifier — M then L — races shipped

Same-turn `remember_fact` `ok` true skips extract persist for that predicate+value identity. LLM `speech_act` remains. Hard classifier is still later L.

Spec: [`specs/phases/148-extractor-dual-write/`](../phases/148-extractor-dual-write/spec.md).

Do not start 149 in the 148 tree.

### 149 — Specialist memory constitution — M — shipped

Calendar, messenger, and news keep `_build_system_prompt` (constitution + job before biography), import companion honesty, and do not add remember/forget tools.

Spec: [`specs/phases/149-specialist-memory-constitution/`](../phases/149-specialist-memory-constitution/spec.md).

Do not start 150 in the 149 tree.

### 150 — Eval `memory_proposals_count` hard-cut — S — shipped

Deleted `EvalChatResponse.memory_proposals_count`. Judges use `tool_calls`. AGENTS.md and CLAUDE.md phase indexes include 140–150.

Do not create `specs/phases/151-*`.

Spec: [`specs/phases/150-eval-guide-honesty/`](../phases/150-eval-guide-honesty/spec.md).

Spec (bundles 151): [`specs/phases/150-eval-guide-honesty/`](../phases/150-eval-guide-honesty/spec.md).

### 151 — AGENTS.md / CLAUDE.md phase-index drift — S

`CLAUDE.md` lists 140–142; `AGENTS.md` does not. That is documentation claiming a different source of truth — same philosophy, not user-facing memory. Size S: sync indexes after 143 lands or in the same docs pass as 150.

Specified with 150: [`specs/phases/150-eval-guide-honesty/`](../phases/150-eval-guide-honesty/spec.md) (no separate 151 directory).

---

## Explicitly not next

- Claude-style `/memories` filesystem.
- Rewriting 140–142 write/read/routing contracts as a bundle.
- Starting P5 inside 143.
