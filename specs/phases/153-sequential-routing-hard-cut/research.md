# Research: Sequential Routing Hard-Cut

**Feature**: `153-sequential-routing-hard-cut`  
**Date**: 2026-09-16

## 1. Delete `plan_sequential` this phase

**Decision:** Remove the node, `after_decompose` mapping, END edge, `plan_sequential` function, `dynamic_plan_steps` / `dynamic_plan_high_risk` on `AgentState` and `turn.py`. WorkflowPlanner remains for the **workflow agent**.

**Rejected:** Keep the node returning a message “use companion instead.” Execute sequential subtasks in `_execute_compound` while also using companion.

## 2. Conductor rewrite rule

**Decision:** If `envelope.is_sequential` and `len(subtasks) > 1`, replace envelope with companion primary, original user prompt, `is_compound=False`, stash former subtasks as `conductor_hint`. Then `fetch_context` as a normal single-agent turn.

**Rejected:** Execute Haiku DAG. `is_sequential` with one subtask → companion (would steal calendar).

## 3. Independent parallel unchanged

**Decision:** `is_compound and not is_sequential` still decompose → fetch_context → capability_check strictest-wins → gather + synthesize.

**Rejected:** Send all compound to companion.

## 4. Companion `description` finally changes

**Decision:** Rewrite embedding text to include coordinating calendar, email, reminders, and loops **by delegating**, plus today’s chat/reasoning. Remove “Not for calendar, email…”.

**Rejected:** Leaving 151 lock forever (mixed turns would not embed to companion).

## 5. Ledger vs 154

**Decision:** 153 adds turn-local list + `MessageTrace` fields. 154 adds panel, progress keys, eval YAML.

**Rejected:** Bundling the React panel into 153.

## 6. Sequential `_execute_compound` branch

**Decision:** Delete it. After rewrite, execute_tool never sees sequential compound. Leaving the branch would be a second sequence owner.

**Rejected:** “Keep for safety.”
