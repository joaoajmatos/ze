# Research: Ingest vs Remember Honesty

**Feature**: `147-ingest-remember-honesty`  
**Date**: 2026-09-16

## 1. Keep MemorySink

**Decision:** Do not route ingest facts through `remember_fact`. Do not import `ze_personal` from `ze-ingestion`. Do **not** lift `enforce_memory_confirmations` into `ze_agents` (144: dialects stay out of `ze-agents`).

**Companion** remains the gated chat speaker (143/145 honesty). **IngestionAgent** hard-cuts instructions and tool descriptions so ingest/extraction language is the only allowed confirmation. Eval fails remember-tool claims on ingest-only turns.

**Rationale:** `ze-ingestion` cannot take a plugin dependency. Sharing the regex via `ze_agents` would put claim dialect in the developer API package.

**Rejected:** `MemorySink` → `remember_fact`; ingest agent importing companion honesty; lifting the gate into `ze_agents`.

## 2. Mixed turns

Earned `remember_fact` `ok` may confirm that preference only, not the file as a whole.

## 3. Eval

Hard-cut `eval/scenarios/memory.yaml`. Do not delete `memory_proposals_count` (150).
