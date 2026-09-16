# Memory honesty roadmap

> **Status:** Living note. Phase 143 is specified separately (`specs/phases/143-memory-claim-honesty/`). This file is not a spec-kit feature. Do not mint 144+ directories from this document until a specify run.
> **Date:** 2026-09-16
> **Related:** [Pre-v1 Hard Cuts](pre-v1-hard-cuts.md), [Ze Doctrine](ze-doctrine.md), Phases [140](../phases/140-memory-admission/spec.md)–[142](../phases/142-speech-act-routing/spec.md)

---

## Context

Phases 140–142 added remember/forget tools, prompt constitution, and speech-act routing. The remaining failures are the same class: Ze **says** something happened in a store, or writes the **wrong** store, without a successful licensed action. Phase 143 closes in-turn “I’ll remember / I forgot” and over-forget matching. Everything below waits until that gate exists, so later work does not police a lie that 143 should already block.

---

## After Phase 143 (ordered)

### 144 — Constraint veto on mail/calendar writes (P5) — M

Standing constraint facts (never email after 22:00) store as biography and do not block or confirm outbound mail or calendar tools. 142 deferred this on purpose. It waits until remembered confirmations are earned so “I won’t send that because of your constraint” is not another unearned line. Suggested size M: intercept messenger/calendar write tools, read reviewed constraint facts, confirm or refuse. Do not start this as 143.

### 145 — Response-level unsolicited recitation — S

141 forbids “I remember that you…” in the **prompt**. The reply can still recite biography unsolicited. Same turn-path idea as 143, after confirmations are gated, so the filter is not confused with remember/forget success language. Size S: extend the companion reply gate (or shared constitution enforcement) to unsolicited recitation; `TurnSurfacing` still owns open items.

### 146 — Forget vs cancel across stores (R14) — M

Users say “forget the dentist” meaning a reminder, loop, or goal. `forget_fact` is biography-only; companion instructions say so, but a miss or a wrong biography hit is still possible. Needs 143’s precise miss plus earned forgotten claims so a domain cancel is not a second fake success. Size M: route cancel speech to reminder/loop/goal tools; do not dual-write forget.

### 147 — Ingest vs remember honesty (R7) — S

Ingest still writes synthesized perception facts via `MemorySink`. The model can talk as if `remember_fact` ran on a PDF. 143 only gates companion tool `ok`. Size S: ingest/companion copy and eval so file ingest is not confirmed as a remember-tool success.

### 148 — Extractor dual-write, then hard speech-act classifier — M then L

Admission `speech_act` is still LLM JSON. Post-turn extraction can still propose facts after an in-turn `remember_fact` (140 allows extraction if predicates dedup). Silent races and a soft classifier are the same honesty family. Wait for 143 so tests distinguish “model lied” from “extractor duplicated.” Size M for dual-write/dedup races; L if replacing the LLM classifier with a hard one.

### 149 — Specialist memory constitution — M

141 rewrote companion and a shared constitution block; calendar, mail, and news catalogs were deferred. Specialists can still narrate memory they cannot write. Size M: constitution + job order on those agents, not a new remember API (142 already forbade extra remember tools on those catalogs).

### 150 — Eval `memory_proposals_count` hard-cut — S

`EvalChatResponse.memory_proposals_count` is always 0. `AgentResult.memory_proposals` is gone. Docs already tell judges to use `tool_calls`. Keeping the field is a compatibility shim. Size S: delete from schema, eval server, clients, tests.

### 151 — AGENTS.md / CLAUDE.md phase-index drift — S

`CLAUDE.md` lists 140–142; `AGENTS.md` does not. That is documentation claiming a different source of truth — same philosophy, not user-facing memory. Size S: sync indexes after 143 lands or in the same docs pass as 150.

---

## Explicitly not next

- Claude-style `/memories` filesystem.
- Rewriting 140–142 write/read/routing contracts as a bundle.
- Starting P5 inside 143.
