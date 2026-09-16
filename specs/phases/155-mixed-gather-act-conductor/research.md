# Research: Mixed Gather+Act → Conductor

**Feature**: `155-mixed-gather-act-conductor`  
**Date**: 2026-09-16

## 1. Same rewrite, extra predicate

**Decision:** Keep one `apply_conductor_rewrite`. Rewrite when `(is_sequential and len(subtasks)>1) or (mixed_gather_act and more than one distinct agent)`. Mixed does not require `is_sequential`.

**Rejected:** A second rewrite function. A Haiku prompt-only fix (“always set sequential on research+email”) — 153 already says Haiku is a hint; engine must not wait for the flag.

## 2. Intent families, not `{research, messenger}`

**Decision:** Classify each subtask `intent` (strip, casefold):

- Gather: `read`, `lookup`, `search`
- Act: `create`, `update`, `delete`, `send`

Mixed iff at least one gather and one act among subtasks **and** more than one distinct `agent`. Motivating fixture remains research `read` + messenger `create`/`send`.

**Rejected:** Allowlist of agent name pairs. Inferring act from Mode.CONFIRM via agent registry (would pull plugin registry into a routing helper and treat calendar create+news read correctly anyway via intents). Treating `manage`/`reason` as act or gather this phase.

## 3. Sequential `len>1` vs mixed unique agents

**Decision:** Sequential rule stays 153: `len(subtasks)>1` even if the same agent appears twice. Mixed rule uses distinct agent names so two research reads are not “mixed specialists.”

**Rejected:** Changing 153’s sequential bar in this phase.

## 4. Independent writes stay parallel

**Decision:** Two act-only specialists with sequential false remain compound (strictest-wins). This phase does not invent write+write conductor routing.

**Rejected:** Sending all multi-act compound to companion (scope creep; parallel gate spec is later).

## 5. Eval

**Decision:** Add `conductor_mixed_gather_act_research_messenger` (sequential false; companion primary; no parallel fan-out). Keep 154 ids.

**Rejected:** Editing 154 sequential scenario to drop `is_sequential`.
