# Primitives — Reference

System One models use three primitive question types. Each returns a different shape of typed answer. The exact request/response shapes vary by provider; this reference describes the concepts that apply across providers.

## Choice

**Use when:** The answer is one of a known set of unordered options.

**Concept:** The model selects one option from a defined set. The answer includes the selected option plus a probability for every option.

**What comes back:**
- The selected option (highest probability).
- A probability distribution across every option (sum = 1).
- A confidence score (0–1) summarizing how peaked the distribution is.

**Design rules:**
- Give each option a description that separates it from other options.
- When two options are easily confused, use structured descriptions with fields for what each covers, what it's not for, and example inputs.
- Include at most 255 options (provider-dependent). Add a catch-all option like `other` or `none_of_the_above` when the list may not cover every input.
- `null` descriptions are acceptable when the option name is self-explanatory.

**Example:** "Which team should handle this ticket?" with options `billing`, `returns`, `shipping`.

## Noul

**Use when:** The answer is yes/no and the probability itself is the useful signal.

**Concept:** A single number representing the probability that the answer is yes (0 = no, 1 = yes).

**What comes back:** A value between 0 and 1. Near 1 is a strong yes, near 0 is a strong no, near 0.5 means yes and no are equally probable.

**Design rules:**
- Ask one yes/no proposition per Noul. Multi-condition questions ("is the customer angry and asking a refund?") should be split into separate Nouls.
- Phrase so a high value = yes. "Does the message contain personal data?" not "Is the message free of personal data?"
- Optional criteria with `true` and `false` descriptions help when the boundary between yes and no is subtle.
- **Noul 0.5 is NOT medium intensity.** It means equal probability. Use Score for degree.
- No separate confidence value: the single `noul` describes the distribution completely (only two outcomes).

**Example:** "Does the customer request a refund?" returning `noul: 0.95`.

## Score

**Use when:** The answer is a position on a described spectrum with ordered steps.

**Concept:** The model picks a position along levels you define, from low to high. The answer is a probability-weighted mean of the level numbers.

**What comes back:**
- `score`: A position on the level number line (0 through top level) that can fall between levels.
- `probabilities`: The probability of each level (sum = 1).
- `confidence`: How peaked the distribution is (0–1).

**Design rules:**
- Describe concrete situations, not abstract degrees. "Broken feature, workaround exists" > "Moderately severe."
- Each level is evaluated independently. The model does not see a level's number or its neighbors.
- 2–10 levels. More is fine if each is distinctly describable.
- Keep each Score to one dimension. Split multi-dimensional judgments into separate Scores.
- Normalize scores by dividing by `len(criteria) - 1` before combining Scores with different level counts.

**Example:** "How severe is this bug?" with levels `cosmetic`, `workaround exists`, `blocking`.

## Structured instructions and criteria

`instructions` and `criteria` entries can be objects or arrays when they need several kinds of guidance. Use structure when:

1. The question needs context or examples alongside it.
2. Part of the question comes from code (e.g., a database record to compare against).
3. Several questions have similar instructions but differ in a code-supplied value.

**Field names are not reserved.** You choose them. Use short names that label what follows: `question`, `focus`, `what`, `not_for`, `examples`, `compare`, etc.

## Asking multiple questions together

All question types can be mixed in one call. Every question sees the same state, is evaluated independently, and returns under its ID. Adding questions barely changes response time — they run in parallel.

**Speculative fan-out:** Ask every question your code might need, including ones whose answer only matters for some inputs. Code ignores irrelevant answers. This has near-zero latency cost and is the most important optimization.
