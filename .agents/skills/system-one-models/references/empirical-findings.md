# Empirical findings — Reference

> Real-world tradeoffs, failure modes, input structuring pitfalls, and model behavior quirks discovered during integration research. These apply broadly across System One models — not just one provider's implementation.

## Input structuring

### State should be the minimum the questions need

System One models suffer from context rot / distraction: accuracy falls as state grows with irrelevant content. Unrelated detail acts as a distractor, and large state makes it harder to tell which part of the input produced a wrong answer.

**Do this:** Retrieve and filter in code first. Send only the fields each question needs. Prefer named JSON fields when state has several parts — reference them with backticked paths like `ticket.messages[0].text`.

**Don't:** Dump the entire database record or conversation history. The model doesn't ignore what it doesn't need — it gets pulled in the wrong direction.

### How you name things matters

Option keys, question IDs, and field names are visible to the model. A key like `bug_report` carries semantic weight — the model can infer meaning from the name itself. This is usually helpful but can bias answers when the key name implies something the description doesn't say.

**Tradeoff:** Descriptive keys help the model understand quickly; they can also override the description if the key and description conflict. Align them.

### Ordering options can influence results

The order of options in a Choice or levels in a Score is not neutral. The model may show primacy or recency effects — options listed first or last can be slightly favored.

**Mitigations:**
- Descriptions that clearly separate options reduce ordering bias. Structured criteria (`what`, `not_for`, `examples`) help more than short strings.
- When running benchmarks, randomize option order across calls and measure variation.
- For production systems where bias matters, pick a stable order (e.g., alphabetical, or risk-ascending) and keep it consistent so bias is at least predictable.
- Score levels must be in order (low to high) — that's inherent to the primitive. But the descriptions themselves can still be tuned.

### The same question phrased two ways may give different answers

A Choice asking "yes or no?" does NOT give the same answer as a Noul asking the same thing. Choice is relative (which option?), Noul is absolute (how probable?). The probability values differ systematically:

- `P(Noul = yes)` and `Choice.probabilities["yes"]` may diverge.
- `P(Noul = refund)` and `1 - P(Noul = not_refund)` rarely sum to 1.

**Pick one formulation and stick with it.** Don't carry a threshold tuned on Noul to a Choice or vice versa.

## Known failure modes

### Literal reading

The model answers the question you wrote, not the one you meant. Scoping words, negations, and implied conditions are read at face value.

**Fix:** State the exact condition in `instructions` — be specific. Put boundary cases in `criteria`. When you look at a wrong answer and find yourself explaining what you really meant, that explanation is the missing half of the instruction. Split ambiguous questions into two literal ones and combine in code.

### No math, no counting, no numeric interpolation

The model does NOT count reliably — characters, occurrences, items in a list. It recognizes the shape of an answer rather than tallying. Error grows with the size of what's being counted.

It also cannot interpolate between Score levels to reconstruct exact numbers, and cannot compare numeric representations (hex values, RGB triples, binary encodings).

**Fix:** Keep ALL arithmetic in code. Count by iterating in code and asking one Noul per item, then summing in code. Convert hex/RGB to named buckets before sending. Date comparison: extract components via Choice (each part is a small closed set), then assemble and compare in code.

### Indirection hurts accuracy

Questions with double negatives, properties of properties, or multi-hop reasoning cost accuracy.

**Fix:** Write instructions as directly as possible. Point to the relevant part of state by name. Reduce hops.

### Contradictory instructions and criteria

When `instructions` and `criteria` ask for different things, the model gets confused. For example, a Noul where `true` maps to no and `false` maps to yes.

**Fix:** Treat criteria as an extension of the instruction. Align them. Aim for language an average person can read and understand.

### Structural invariance is not guaranteed

The model is consistent (similar outputs for similar inputs) but does NOT satisfy logical identities you might assume:

- A question and its negation across two Nouls: `P(question) + P(negation) ≈ 1` is NOT guaranteed.
- The same question as a Noul and as a yes/no Choice may give different probability values.

**Fix:** Don't rely on structural identities. Word questions to mean directly what you want. Use the same primitive consistently for a given judgment.

### Adversarial content in state

State is data, and the model does not treat it as hostile by default. Injected instructions, deliberately misleading framing, or text arguing for its own classification can move the answer.

**Fix:** Be explicit in criteria. Write precise prompts. Test edge cases before deploying to many users.

## Tradeoffs

### More questions ≈ same latency, more tokens

Adding questions to a single request barely changes response time (most queries complete in ~100ms regardless of count). But more questions = more input + output tokens = higher cost. **The tradeoff is cost vs. completeness, not cost vs. speed.**

**Strategy:** Send every question your code might need (speculative fan-out). The latency benefit over sequential requests is enormous; the token cost is the price of the intelligence you need.

### Structured criteria improve accuracy but cost tokens

Short string descriptions are cheap and sufficient for unambiguous options. Structured objects with `what`, `not_for`, `examples` improve accuracy on easily confused options but consume more input tokens.

**Strategy:** Use strings for obviously distinct options; add structure where the model confuses boundaries.

### Calibration is aggregate, not per-prediction

System One models are trained for calibrated probabilities overall — the probability values match observed frequencies across groups. But any individual prediction can be wrong. Calibration does not mean correctness.

**Strategy:** Validate on your own data. Confidence thresholds are tuning parameters, not guarantees.

### Score outputs are semantically useful, numerically weak

The `score` value (probability-weighted mean of level numbers) is useful for ranking and thresholding. But the exact numeric position should NOT be treated as a precise measurement — levels are evaluated independently and the model does not see level numbers.

**Strategy:** Use Score for ranking and classification, not for recovering exact quantities by interpolating between levels.

## Question decomposition

### Broad questions hide several judgments behind one answer

A single question like "Is this spam?" collapses many independent signals (credential requests, unexpected rewards, sender mismatch, link deception, urgency framing) into one yes/no. You lose the ability to inspect, tune weights per signal, or route on specific patterns.

**Fix:** Decompose into one Noul per signal. Combine with weighted thresholds in code.

### Atomic does not mean one sentence

A narrow, coherent judgment is atomic. A bounded action selection or contextual interpretation can be several sentences as long as it evaluates one property. Splitting independently useful dimensions is good; destroying the relationship being judged (e.g., splitting a comparison into two unrelated absolute judgments) is bad.

## Option and level design

### Always include a fallback option

When the answer may not be in your set, include `other`, `none_of_the_above`, or `not_applicable`. Without one, the model still picks the closest option — silently.

### Source-value selection needs complete candidates

If the model must choose from source candidates, the candidates must be exhaustive. The model cannot choose an omitted value. Use regexes, parsers, or lookups to generate candidates in code, then let the model select.
