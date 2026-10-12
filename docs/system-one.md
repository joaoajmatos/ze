# Ze — System One

System One is a small model that answers closed questions. It never writes text. It returns a choice among labels, a yes/no probability, or a score. Ze uses it as a fast gate in four places. Code makes every final decision.

This page explains the layers around it, the three question types, where Ze asks the questions, and how Ze handles a failure. For setup and tuning, see [configuration.md](configuration.md#system_one).

---

## Where it fits

Ze already has four ways to make a semantic choice. System One adds a fifth.

| Layer | Job | Output |
|---|---|---|
| Local E5 embeddings | Rank agents, skills, and memories by similarity | A cosine score. It measures closeness, not certainty |
| Local NLI cross-encoder | Test whether one sentence supports or contradicts another | Entailment and contradiction scores |
| System One | Pick one label, or judge one yes/no question, on a short list | A label with a probability, calibrated on Ze data |
| LLM through OpenRouter | Write: replies, drafts, summaries, plans | Text |

Four rules keep the layers apart:

1. **System One is not an LLM.** Ze never sends it as a chat completion. OpenRouter hosts it at `POST /api/v1/systemone`, and Ze uses the same `OPENROUTER_API_KEY`.
2. **E5 stays the shortlist.** System One chooses among the few candidates E5 ranks highest. It does not replace the embeddings.
3. **NLI stays for contradiction checks.** System One does not replace it.
4. **Code owns policy.** Budgets, capability gates, confirmations, windows, and writes never depend on a model.

---

## Question types

Ze sends one request with up to a few named questions. The client is `SystemOneClient` in `ze_agents/system_one.py`.

| Type | Answer | Use it for |
|---|---|---|
| **Choice** | One label from a closed set, a probability for each label, and a confidence | Which agent, which kind of statement, which skill |
| **Noul** | The probability of yes. About 0.5 means undecided | An independent yes/no, such as "does this state a fact about the user?" or "does this text leave something open?" |
| **Score** | A degree on ordered, described levels | How complex a request is |

For a Choice, the confidence says how peaked the distribution is. A confidence near 1 means the model strongly prefers one label. Code compares this number with a bar. A Noul has no separate confidence, and Ze compares its probability with a different bar. The two bars are never the same number.

Each request carries a small state: named fields such as the user's words, a short history, and a few hints, each capped in length. Ze never sends a full session or database row.

---

## The client

`SystemOneClient.evaluate(state, questions, max_attempts=None)` returns a `SystemOneResult`. The result has an outcome, either `ok` or `skip`.

- `ze_core/openrouter/system_one.py` holds `OpenRouterSystemOneClient`. It posts to OpenRouter with the model from `system_one.model` (default `typesafe/jev-1.13`) and a timeout per attempt (default 2000 ms).
- `DisabledSystemOneClient` answers every call with a skip for reason `disabled`. `build_system_one_client` returns it when `system_one.enabled` is false.
- Ze retries a request on status 429, 500, 502, 503, 504, and 529, up to three attempts, with waits of 1, 2, and 4 seconds. Every surface today passes `max_attempts=1`, so none of them retries.
- The client records the token cost of each answer in the cost tracker.

`ze-memory`, `ze-skills`, `ze-worldstate`, and `ze-core` depend only on the Protocol in `ze-agents`. Plugins reach it through `ze_sdk`.

---

## Fail-open rule

A skip is not an error. A skip happens when the master switch is off, the key is missing, the call times out, the service is overloaded, the call fails, the request is invalid, or the answer is malformed. On a skip, Ze does what it did before System One existed. No surface blocks a turn.

---

## The four surfaces

Each surface follows the same pattern. Code builds the shortlist or the candidate. One request asks the questions. A pure function, `decide()`, turns the answers into an action using bars from `config.yaml`. If a bar is `null`, the surface counts as uncalibrated and skips.

| Surface | Runs in | Questions | Possible actions |
|---|---|---|---|
| **Speech act** (phase 163) | After the turn, in the memory extractor (`ze_memory/speech_act_judge.py`) | Choice: speech act. Choice: fact family. Noul: biography | persist, hold, skip |
| **Routing** (phase 164) | The `embed_route` node (`ze_core/routing/judge.py`) | Choice: agent (shortlist plus `none`). Noul: needs more than one specialist. Score: complexity | trust, decompose, abstain, skip |
| **Skills** (phase 166) | The `match_skills` node (`ze_skills/judge.py`) | Choice: skill (shortlist plus `none`). Noul: needs a skill | apply, drop, abstain, skip |
| **Loop gate** (phase 168) | The `write_memory` node for conversation; the email, calendar, and ingestion extractors for the rest (`ze_worldstate/loop_judge.py`) | Noul: open concern. Noul: resolves an existing loop. Noul: explicit declaration (conversation only) | create declared, create suspected, resolve, hold, fallback |

### Speech act

The extractor decides whether a finished turn states a durable fact worth keeping. System One answers three questions: what kind of statement it is, which fact family it belongs to, and whether it is a biography fact. Code keeps the fact only when the statement is a fact, the family is one Ze admits, and each answer clears its bar (`choice_hold` and `biography_hold`). When the answers say persist, a Haiku call writes the fact text, because System One cannot write. When System One skips, Ze runs the older Haiku judge once. An unsure answer holds the fact. It does not fall back to Haiku.

### Routing

E5 ranks the agents, and the top `shortlist_k` go to System One. A confident choice of one agent routes the turn straight to it. A `none` answer, or a high multi-specialist probability, sends the turn to the Haiku decompose step. An unsure choice falls back to the E5 threshold rules. Each agent can declare `routing_criteria`, a use-for and not-for text the choice reads in place of its `description`. At the shipped `shortlist_k` of 9 on a 10-agent roster, E5 filters little for the choice; it still drives the cosine skip path. The complexity score picks the model tier only when `complexity_lookup_max` is set; it ships unset. When System One routes a turn, the routing log stores the choice confidence instead of the cosine score.

### Skills

E5 keeps the skills at or above `shortlist_floor`, up to `shortlist_k`. System One then picks one skill or `none`, and says whether the request needs a skill at all. A confident choice plus a high enough need applies at most one automatic skill. An unsure answer or a skip falls back to the older rule, where every skill above `skills.match_threshold` applies. A skill named with `/skill-name` skips this step and always applies.

### Loop gate

Open-loop extraction decides whether a piece of text leaves something unfinished: a promise, a task, a lingering concern. Before phase 168, one Haiku call answered that question and wrote the title. Now System One asks three independent yes/no questions in one request:

- `is_open_concern`: the text implies an unfinished commitment, task, or concern.
- `resolves_existing`: the text reports a previously open commitment as done.
- `explicit_declaration`: the user declares the commitment themselves. Ze asks this only for conversation text.

Each question has its own bar (`loop_hold`, `resolves_hold`, `explicit_hold`). Code decides in this order: a high `resolves_existing` closes a matching loop; a low `is_open_concern` holds; a high `explicit_declaration` creates an active, user-declared loop; anything else creates a suspected loop. A positive answer then calls Haiku to write the title, and to suggest a window in days for a new loop. Haiku never decides whether a loop exists. Matching, dismissed-loop checks, confidence, and drift stay in code.

Conversation runs the gate in the `write_memory` node, beside the fact extractor, and records its rows in the message trace. Trivial turns skip the request. Email, calendar, and ingestion run the same gate. They can create suspected loops and resolve existing ones, log their judgments, and write no message-trace rows. When the surface is off, uncalibrated, skipped, or returns an invalid answer, Ze runs the older Haiku gate.

---

## Status

| Surface | Shipped config | Why |
|---|---|---|
| Speech act | On, with `choice_hold: 0.9` and `biography_hold: 0.7` | Calibrated on 60 English and Portuguese rows on 2026-10-09 |
| Routing | On, with `choice_trust: 0.5`, `multi_specialist_hold: 0.5`, `shortlist_k: 9` and `complexity_lookup_max: null` | Phase 167 calibrated on 52 held-out English and Portuguese rows on 2026-10-12: zero research-to-companion misses, zero harmful trusts, ECE of 0.080 and 0.013. Raw English accuracy on `routing_holdout` is 0.90, and its one miss falls back to decompose. The complexity bar stays unset, so the word-count classifier picks the model tier |
| Skills | On, with `choice_trust: 0.75`, `needs_skill_hold: 0.6` and `shortlist_k: 5` | Calibrated on 84 English and Portuguese rows on 2026-10-12: zero wrong applies |
| Loop gate | Off, with `loop_hold`, `resolves_hold`, and `explicit_hold` all `null` | Ze enables it only after `make calibrate-loop-gate` returns an `ENABLE` verdict on a held-out set for English and Portuguese |

Calibration scripts live in `eval/calibration/`. Each one runs the labeled set against the live service and costs credits:

```bash
make calibrate-speech-act
make calibrate-routing
make calibrate-skills       # add --recall for the offline shortlist check
make calibrate-loop-gate    # tuned set by default; --set holdout gives the verdict
```

---

## Trace

Every judgment appears in the message trace as a `JudgmentTrace` row: the question id, the kind, the latency, the answer, the probabilities, the peakedness, the model, the token count, whether code used the answer (`consumed`), and the skip reason. `embed_route` and `match_skills` add their rows to `state["judgments"]`. The speech-act and loop-gate rows are added after the turn. The trace panel in `ze-web` shows them. Use them to see why Ze routed a turn, applied a skill, or kept a fact.

---

## What System One never does

It never writes replies, drafts, or plans. It never replaces the capability gate, the confirmation flow, the spend budget, the write-time contradiction check, or any date or window math. A probability of 0.62 does not license Ze to state a suspicion as a fact. Claim kinds on contributions still decide how Ze may surface a claim.

---

## Further reading

- [specs/arch/system-one-models.md](../specs/arch/system-one-models.md) — pinned decisions and the queue of later uses
- [configuration.md](configuration.md#system_one) — keys, bars, and calibration steps
- [skills.md](skills.md#automatic-matching-with-the-system-one-gate) — the skill gate in detail
- [memory.md](memory.md) — fact admission and the speech-act gate
- [cognitive-architecture.md](cognitive-architecture.md) — open loops and where the loop gate sits
