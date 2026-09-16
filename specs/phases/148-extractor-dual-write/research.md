# Research: Extractor Dual-Write and Dedup Races

**Feature**: `148-extractor-dual-write`  
**Date**: 2026-09-16

## 1. Live skip is too weak

**Finding:** `_remembered_predicates` skips extractor proposals when `remember_fact` `ToolCall.success` is true, keyed only on `args.predicate` (lowercased). It ignores payload `ok`, value identity, and JSON-string results.

**Decision:** Replace that filter in place. Skip extract persist when `remember_fact` payload `ok` is true and identity matches (predicate + value after 140 normalize).

**Rejected:** Flag the old predicate-only skip beside a new rule. Non-LLM speech-act classifier.

## 2. Identity

**Decision:** Reuse Phase 140 predicate/value identity (strip/casefold). Do not merge different predicates that share a value. Punctuation/casing follows existing 140 normalize if present.

## 3. Test split

**Decision:** Model-lie fixtures stay in companion honesty tests (reply wording). Duplicate-race fixtures live in ze-core `test_extractor_dual_write.py` (store cardinality). Names must not overload.

## 4. Failed remember

**Decision:** `ok` false does not uniquely imply extraction should write; 140 admission still applies. Failed tool is not a second remember door.

## 5. Out of scope

Hard classifier (later L). 144–147, 149. Global cross-turn merge product.
