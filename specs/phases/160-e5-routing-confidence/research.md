# Research: E5 Routing Confidence

**Feature**: `160-e5-routing-confidence`  
**Date**: 2026-09-16

## 1. Do not swap the model again

**Decision:** Keep `E5Embedder` / `intfloat/multilingual-e5-base` / `query:` / `passage:`. 160 only calibrates confidence and hard-cuts MiniLM docs.

**Rejected:** Loading MiniLM beside E5; `e5-small` swap in this phase.

## 2. Defaults, not YAML-only

**Decision:** `config.yaml` already sets `routing.gap_threshold: 0.03` because “E5 scores compress into 0.73–0.86; 0.10 gap was MiniLM.” Framework `ROUTING_GAP_THRESHOLD` is still 0.10 and `ROUTING_THRESHOLD` is still 0.55. Tests and a missing YAML block therefore still behave like MiniLM. Lift the calibrated pair into `ze_agents.defaults`; YAML may repeat, not uniquely own, the values.

**Rejected:** Leaving 0.10 in code and “just documenting the YAML overlay.”

## 3. Measure both floor and gap

**Decision:** Threshold 0.55 is *below* the E5 band, so almost everything clears the floor; the MiniLM-sized **gap** is what still forces `is_compound`. Implement may also raise the floor into the E5 band so a mediocre match is not “confident.” Record the chosen pair in defaults + YAML together.

**Rejected:** Copying 97’s hoped 0.60 without measuring; deleting Haiku decompose.

## 4. Conductor rewrite is a consumer, not the change

**Decision:** 153/155 stay. Success is fewer false `is_compound` envelopes reaching `apply_conductor_rewrite`.

**Rejected:** Tweaking rewrite predicates to ignore low-gap compounds.
