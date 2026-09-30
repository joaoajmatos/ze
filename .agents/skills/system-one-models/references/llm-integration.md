# System One + LLM (System Two) integration — Reference

> How System One models and LLMs complement each other in the same architecture.
> System One handles fast, bounded, calibrated judgments. LLMs handle open-ended
> generation, reasoning chains, and tasks that can't be constrained to a fixed set
> of outputs.

## The high-level split

| Dimension | System One | LLM (System Two) |
|-----------|------------|------------------|
| Output | Typed, constrained, probabilities | Free text, code, reasoning |
| Speed | ~100ms per call | Seconds to tens of seconds |
| Cost | Pennies per thousand calls | Dollars per million tokens |
| Certainty | Calibrated probabilities | No built-in uncertainty signal |
| Best for | Classification, selection, scoring, yes/no decisions | Generation, summarization, reasoning chains, explanation |

The two are not competitors — they're complementary. Code owns the workflow and delegates to whichever model suits each step.

## Cascade patterns

### 1. System One gates access to the LLM

The cheapest and most impactful pattern. System One decides whether an LLM call is needed at all.

```
Input → System One (classify, score) → code decides → LLM (if needed) → output
```

**Examples:**
- Screen input before it reaches the LLM: if your guardrail Noul scores > 0.8 for harmful content, block before the LLM ever sees it. (Inverse: screen LLM output before showing to user.)
- Only call the expensive reasoning model when the System One confidence is too low: `if answer.confidence < 0.6: route_to_llm(input)`.
- Only summarize documents that pass a relevance threshold: one Noul per document, sort, take top N, send only those to the summarizer.

```python
# Input guardrail: block before LLM spends tokens
response = client.system_one(state=user_message, questions={
    "contains_pii": Noul(instructions="Does the input contain personal data?"),
    "is_harmful": Noul(instructions="Is the input harmful or abusive?"),
    "needs_llm": Noul(instructions="Can this be answered deterministically?"),
})

if response.answers["is_harmful"].noul > 0.8:
    return block_request("Content policy violation")
if response.answers["needs_llm"].noul < 0.6:
    return handle_deterministically(user_message)
return route_to_llm(user_message)
```

**Rationale:** Most inputs don't need an LLM. System One filters them for a fraction of the cost. See the [guardrails cookbook](https://docs.typesafe.ai/cookbooks/llm_guardrails.md) for a full example.

### 2. LLM produces candidates, System One selects

The LLM generates options (open-ended, creative), then System One picks the best one (bounded judgment, calibrated).

```
Input → LLM (generate candidates) → code extracts candidates → System One (select best) → output
```

**Examples:**
- LLM generates 5 potential email subject lines → System One selects the best by relevance/effectiveness.
- LLM extracts possible entity values from free text → regex normalizes them → System One picks the correct one from the pre-parsed options.
- LLM suggests 3 possible tool calls → System One scores each for correctness and picks the most likely.

**Rationale:** Generation is what LLMs are good at. Selection is what System One is good at. Don't ask the LLM to do both — it has no calibration for its own confidence in a choice.

### 3. System One scores LLM output quality or accuracy

The LLM generates, System One verifies or scores the result.

```
Input → LLM (generate) → output → System One (verify/score) → verdict
```

**Examples:**
- [Citation checking](https://docs.typesafe.ai/cookbooks/citation_check.md): LLM generates a claim with a citation → System One checks whether the cited source supports the claim.
- [SDE cascade](https://docs.typesafe.ai/cookbooks/sde_cascade.md): Lightweight LLM extracts structured data → System One verifies each field → only the uncertain/incorrect fields are sent to a larger LLM for re-extraction.
- LLM summarizes a document → System One scores accuracy, completeness, and faithfulness as separate Nouls.
- LLM answers a user question → System One checks whether the answer addresses the question (Noul) and whether it hallucinated any unsupported claims.

```python
# Check LLM output quality
response = client.system_one(state={
    "question": user_question,
    "document": source_document,
    "llm_answer": llm_output,
}, questions={
    "addresses_question": Noul(instructions="Does `llm_answer` address `question`?"),
    "faithful_to_document": Noul(instructions="Is every claim in `llm_answer` supported by `document`?"),
    "contains_hallucination": Noul(instructions="Does `llm_answer` assert anything not found in `document`?"),
})

quality = (
    0.4 * response.answers["addresses_question"].noul
    + 0.4 * response.answers["faithful_to_document"].noul
    + 0.2 * (1 - response.answers["contains_hallucination"].noul)
)

if quality < 0.7:
    return regenerate_with_higher_temperature(user_question, source_document)
return llm_output
```

### 4. System One routes to the right LLM or prompt

One System One call determines which model, prompt template, or tool set to use — then code dispatches.

```
Input → System One (classify) → code routes → LLM-A (specialist) or LLM-B (general) or deterministic handler
```

**Examples:**
- Classify query complexity: simple Q&A → cheap fast LLM; complex analysis → expensive reasoning model.
- Classify domain: legal question → LLM with legal prompt + document context; medical → LLM with medical prompt.
- Classify language: English → LLM; Spanish → route to Spanish-specialist model.

```python
# One System One call routes to the right handler
response = client.system_one(state=user_input, questions={
    "complexity": Choice(
        instructions="How complex is this query?",
        criteria={
            "simple": "Factual question, can be answered from a single source",
            "moderate": "Needs synthesis across a few sources",
            "complex": "Needs multi-step reasoning or analysis",
        },
    ),
    "domain": Choice(
        instructions="What domain does this query belong to?",
        criteria={"general": "...", "legal": "...", "medical": "...", "technical": "..."},
    ),
})

if response.answers["complexity"].choice == "simple":
    return fast_llm(user_input)
if response.answers["domain"].choice == "legal":
    return legal_llm(user_input, legal_context)
return reasoning_llm(user_input)
```

### 5. Ensemble: System One scores feed LLM context

System One scores become structured input to the LLM, giving it pre-computed signals it can reason over.

```
Input → System One (score multiple dimensions) → code formats scores → LLM (reason with scores) → output
```

**Examples:**
- Product review: System One scores helpfulness, toxicity, and sentiment → LLM writes a moderation decision explaining why.
- Customer ticket: System One scores frustration, urgency, and topic → LLM drafts a personalized reply incorporating those signals.
- Document set: System One scores each document for relevance to a query → LLM synthesizes findings from the top-ranked documents.

**Rationale:** The LLM gets pre-computed high-quality features rather than needing to derive them from raw text. This is cheaper and more reliable than asking the LLM to both extract signals and reason about them.

## When to use which

```
Is the output a fixed set of options?       → System One
Is the output free text or code?            → LLM
Does the task need calibrated uncertainty?  → System One
Does the task need creative generation?     → LLM
Is speed critical (<200ms)?                 → System One
Is the task a reasoning chain >3 steps?     → LLM (or System One cascade)

Can you decompose into a judgment + generation?  → System One for judgment, LLM for generation
Can you check LLM output with a judgment?        → LLM for generation, System One for verification
```

## The SDE cascade (worked example)

The [SDE cascade cookbook](https://docs.typesafe.ai/cookbooks/sde_cascade.md) demonstrates the most elaborate form:

1. **Mini LLM** extracts structured data from text (fast, cheap, may have errors).
2. **System One** verifies each extracted field independently (Noul per field, ~100ms).
3. **Code checks confidence:** fields with confident passes → accepted. Fields with low confidence → routed to reasoning LLM.
4. **Reasoning LLM** re-extracts only the failed fields with full context.
5. **System One** verifies the corrected fields.
6. **Code assembles** final record.

This gets ~90% of the quality of a pure reasoning-LLM approach at a fraction of the cost. The key insight: System One verifies cheaply even when extraction is wrong.

## Cost comparison

| Strategy | Approximate cost per 10k inputs |
|----------|-------------------------------|
| Send everything to LLM | $50–$200 (depends on model + output length) |
| System One filter → LLM cascade | $1–$20 (only 10–30% reach the LLM) |
| System One verification of LLM output | ~$0.10 for judgment, LLM cost unchanged |
| Full SDE cascade | ~1/10th of pure LLM extraction |

Actual costs vary by input length, output length, provider pricing, and pass-through rates. Measure on your own data.
