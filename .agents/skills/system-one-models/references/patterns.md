# Patterns — Reference

> Architectural patterns for building systems with System One models.

## Speculative Fan-Out

**What it does:** Send many questions in a single call, including speculative ones. Code decides relevance after the fact.

**Benefits:** Cost, Speed

**How it works:**
All questions run in parallel against the same state (~100ms per call regardless of question count). Code reads relevant answers and ignores the rest.

```
category = "bug_report" | "billing" | "feature_request"
bug_severity   ← only consumed when category == "bug_report"
refund_likely  ← only consumed when category == "billing"
```

**When NOT to use:** When a later judgment requires new data based on an earlier answer (hierarchical classification, multi-step extraction).

---

## Confidence-Gated Routing

**What it does:** Use confidence as a second decision axis alongside the answer.

**Benefits:** Reliability, Safety

**How it works:**
- Low confidence on any action: send to human.
- Each action has its own confidence threshold based on consequences.
- Same answer, different confidence → different behavior.

```python
if action.confidence < 0.5:
    route_to_human()
elif action == "approve_transfer":
    approve() if action.confidence > 0.85 else ask_confirm()
elif action == "check_balance":
    show_balance()
```

---

## Composite Scoring

**What it does:** Break a complex judgment into atomic Scores on independent dimensions. Combine with weights in code.

**Benefits:** Cost, Reliability, Speed

**How it works:**
1. Ask one Score per independent dimension (e.g., Python depth, leadership, system design).
2. Normalize each score by `len(criteria) - 1` to put all on 0–1.
3. Combine with application-specific weights: `0.4 * py + 0.3 * lead + 0.3 * arch`.
4. Weights live in code. Change them without rerunning inference.

```python
normalized = answers["python_depth"].score / 4  # 5 levels → 0–4
ic_score = 0.4 * py + 0.1 * lead + 0.4 * arch + 0.1 * generalist
```

---

## Intent Routing

**What it does:** Classify requests and route each to the optimal handler: deterministic code, specialist LLM, or human.

**Benefits:** Cost, Speed

**How it works:**
One Choice classifies the intent. Code dispatches to the appropriate handler:
- Fast path: deterministic code (e.g., database lookup).
- Medium path: specialist LLM with domain context.
- Slow path: human agent for complex or sensitive cases.

Optionally score complexity to decide between automated and human handling.

---

## LLM Cascade

See [references/llm-integration.md](llm-integration.md) for the five cascade patterns: gating, candidate selection, output verification, routing, and ensemble features.
