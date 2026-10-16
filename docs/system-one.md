# Ze — System One

System One is a small model that answers closed questions. It never writes text. It returns a choice among labels, a yes/no probability, or a score. Ze uses it as a fast gate in five places. Code makes every final decision.

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
4. **Code owns policy.** Budgets, write confirmations, windows, and writes never depend on a model.

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

## The five surfaces

Each surface follows the same pattern. Code builds the shortlist or the candidate. One request asks the questions. A pure function, `decide()`, turns the answers into an action using bars from `config.yaml`. If a bar is `null`, the surface counts as uncalibrated and skips.

| Surface | Runs in | Questions | Possible actions |
|---|---|---|---|
| **Commitment intake** (phase 173) | After the turn, in the `write_memory` node (`ze_worldstate/intake.py`, `ze_worldstate/commitment_judge.py`) | Choice: commitment. Choice: fact family. Noul: biography. Noul: open concern. Noul: explicit declaration. Noul: resolves an existing loop | persist fact, create declared loop, create suspected loop, resolve, link, hold, fallback |
| **Routing** (phase 164) | The `embed_route` node (`ze_core/routing/judge.py`) | Choice: agent (shortlist plus `none`). Noul: needs more than one specialist | trust, decompose, abstain, skip |
| **Complexity** (phase 182) | The `choose_tier` node, after `match_skills` (`ze_core/routing/tier.py`) | Noul: needs deep reasoning | light model, full model |
| **Skills** (phase 166) | The `match_skills` node (`ze_skills/judge.py`) | Choice: skill (shortlist plus `none`). Noul: needs a skill | apply, drop, abstain, skip |
| **Loop gate** (phase 168) | The email, calendar, and ingestion extractors (`ze_worldstate/loop_judge.py`) | Noul: open concern. Noul: resolves an existing loop | create suspected, resolve, hold, fallback |
| **Corroboration** (phase 172) | Both suspected match paths in `ze_worldstate/extraction.py` (`ze_worldstate/corroboration_judge.py`) | Noul: same concern | corroborate, promote, not same, fallback |

### Commitment intake

After each non-trivial conversation turn, one request asks what the user's message committed them to. Before phase 173, two separate requests judged the same message. The speech-act judge (phase 163) asked which kind of act it was. The loop gate (phase 168) asked whether it opened a loop. They never saw each other's answer, so "remind me at 5pm to call Ana" made a reminder and also a declared loop. The commitment intake replaces both for conversation.

One request carries six questions, and the code reads only the ones the first answer makes relevant:

- `commitment`, a Choice: `reminder`, `loop`, `goal`, `waiting_on`, `fact`, `forget`, `ingest`, `clarify`, or `none`.
- `family` (Choice) and `biography` (Noul): the fact questions from phase 163. Code reads them when the commitment is `fact`.
- `is_open_concern` and `explicit_declaration` (Noul): the loop questions from phase 168. Code reads them when the commitment is `loop`.
- `resolves_existing` (Noul): whether the message reports an open commitment as done. Code reads it for every turn.

A pure function, `decide()`, merges the answers with what the turn already did. Code reads the turn's tool calls. It decides in this order:

1. A high `resolves_existing` closes a matching loop. A `waiting_on` commitment never resolves, because "waiting for her reply" says the matter is still open.
2. If the turn already created a reminder or a goal, Ze creates no loop and persists no fact. It links an existing or would-be loop to the reminder or goal instead. One turn can create a reminder and a goal, and Ze links both.
3. A `waiting_on` commitment is held. Ze only labels it. Tracking what the user awaits is a later phase.
4. A confident `reminder` or `goal` with nothing created is held with the reason `reminder_not_created` or `goal_not_created`. An unsure one goes to the loop rules below.
5. A confident `fact` follows the phase 163 rules: the `family` and `biography` answers must clear their bars, and a Haiku call then writes the fact text.
6. `forget`, `ingest`, `clarify`, and `none` are held, each with its own reason.
7. A `loop` needs `is_open_concern` at or above `loop_hold`, or Ze holds it. A turn where `track_loop` or `confirm_loop` succeeded is held too, because the user's own ask already wrote the loop. Otherwise `explicit_declaration` at or above `explicit_hold` creates an active, user-declared loop, and anything else creates a suspected loop. A Haiku call writes the title.

A commitment answer below `choice_hold` is held as unsure and never goes to Haiku. The one exception is an unsure `reminder` or `goal`, which goes to the loop rules. A skip, an invalid answer, an unset bar, or a surface that is off runs the older paths: the Haiku fact extractor and the phase 109 Haiku loop gate. The extractor's Haiku fallback labels a message `fact`, `forget`, `ingest`, `clarify`, or `none`. The request makes one attempt, no retries.

Ze records the judgment rows and an outcome row on the message trace, and runs the loop commit after the episode exists, without blocking the reply. On the held-out set, about half of the implied conversation loops were created as active, user-declared loops instead of suspected ones (10 of 21 in English, 13 of 21 in Portuguese, fewer than the old gate made), so they skip the suspected path. A follow-up will narrow declarations.

A loop that links to a reminder stores the reminder id on the loop (`reminder_id`, migration `zw004`), beside the existing `goal_id`. The `/loops` page shows a chip for each link.

### Routing

E5 ranks the agents, and the top `shortlist_k` go to System One. A confident choice of one agent routes the turn straight to it. A `none` answer, or a high multi-specialist probability, sends the turn to the Haiku decompose step. An unsure choice falls back to the E5 threshold rules. Each agent can declare `routing_criteria`, a use-for and not-for text the choice reads in place of its `description`. At the shipped `shortlist_k` of 9 on a 10-agent roster, E5 filters little for the choice; it still drives the cosine skip path. When System One routes a turn, the routing log stores the choice confidence instead of the cosine score. Routing always assigns the agent's full model. The model tier is a separate step; see [Complexity](#complexity).

### Complexity

The `choose_tier` node runs after `match_skills`. It asks one question, `needs_deep_reasoning`, and swaps in the agent's `model_simple` only when the answer is at or below `simple_max`. The request holds six fields: the task, the recent conversation, the resume recap, memory, focus and the active skill. Ze makes one attempt, with no retries.

Ze asks only when the turn has exactly one subtask, is not compound, has no conductor hint, and the agent declares a `model_simple` that differs from its `model`. Every other outcome keeps the full model. Those outcomes are: the surface off, an uncalibrated surface, a skip, a timeout, a malformed answer and an error. The shipped config turns the surface on at `simple_max` 0.40, after a held-out ENABLE in English and Portuguese on 2026-10-16. Without a `complexity` config block, the code default is off. The bar is chosen on the tuned set only. Details and the calibration commands are in [Configuration](configuration.md#surfacescomplexity).

### Skills

E5 keeps the skills at or above `shortlist_floor`, up to `shortlist_k`. System One then picks one skill or `none`, and says whether the request needs a skill at all. A confident choice plus a high enough need applies at most one automatic skill. An unsure answer or a skip falls back to the older rule, where every skill above `skills.match_threshold` applies. A skill named with `/skill-name` skips this step and always applies.

### Loop gate

Open-loop extraction on email, calendar events, and ingested content decides whether a piece of text leaves something unfinished: a promise, a task, a lingering concern. Before phase 168, one Haiku call answered that question and wrote the title. Now System One asks two independent yes/no questions in one request:

- `is_open_concern`: the text implies an unfinished commitment, task, or concern.
- `resolves_existing`: the text reports a previously open commitment as done.

Each question has its own bar (`loop_hold` and `resolves_hold`). Code decides in this order: a high `resolves_existing` closes a matching loop; a low `is_open_concern` holds; anything else creates a suspected loop. A positive answer then calls Haiku to write the title, and to suggest a window in days for a new loop. Haiku never decides whether a loop exists. Matching, dismissed-loop checks, confidence, and drift stay in code.

Email, calendar, and ingestion run the gate. They can create suspected loops and resolve existing ones, log their judgments, and write no message-trace rows. Only a user can declare a loop, so these inflows never ask `explicit_declaration`. When the surface is off, uncalibrated, skipped, or returns an invalid answer, Ze runs the older Haiku gate. That gate strips the code fence Haiku wraps around its JSON. Before phase 168 it did not, all 136 replies in the calibration runs failed to parse, and loop extraction created no loops in production.

Conversation no longer uses this gate. Since phase 173 the commitment intake judges conversation turns, with its own loop bars.

### Corroboration

When the gate admits a text as a concern and it matches a `suspected` loop, Ze first decides in code whether the text is an independent source: its source key is new to the loop, its evidence is not already linked, and its key is not on a matching dropped loop. A non-independent match makes no request.

For an independent match, one System One Noul, `same_concern`, asks whether the text is about the same unfinished matter as the loop title. The state holds the loop title (capped at 200 characters), the new text's inflow, and the text capped with the 168 per-inflow caps. Ze makes one attempt. Code decides against two bars:

- At or above `corroborate_hold`: Ze links the evidence and raises the loop's confidence, capped at 0.6. The loop stays `suspected`.
- At or above `promote_hold`: Ze does the same, then promotes the loop to `active` at confidence 0.7 with a 7-day drift deadline.
- Below both, or a skip, an invalid answer, or a failure: the plain evidence link. Promotion changes open-loop state only; it is never a fact.

Ze stores each counted score on the loop's `open_loop_sources` row (score, model, latency) and logs the judgment as `corroboration_judgment`. The conversation commit is fire-and-forget, so these judgments do not reach `MessageTrace.judgments`.

---

## Status

| Surface | Shipped config | Why |
|---|---|---|
| Commitment intake | On, with `choice_hold: 0.7`, `family_hold: 0.7`, `biography_hold: 0.55`, `loop_hold: 0.6`, `explicit_hold: 0.95` and `resolves_hold: 0.8` | Calibrated 2026-10-16 on 160 tuned rows, then judged once on 147 blind held-out rows (73 English, 74 Portuguese) at these frozen bars. Verdict `ENABLE` in both languages. Duplicate bookings: 0 (the old pipeline made 5 and 3). False loop creates: 0 (old: 3 and 3). Fact precision 1.00 in both languages. Fact recall 0.81 and 0.76 (old: 0.71 and 0.57). Loop precision 1.00 (old: 0.73 and 0.79). Loop recall 22 of 22 in both. Choice accuracy 1.00. Rows where the user is waiting on someone wrote nothing in 7 of 7 rows per language. Two earlier held-out sets returned `KEEP OFF`. After each, the wording was fixed on the tuned set only and a new blind set was written. Those two sets are spent and never used for a verdict again |
| Routing | On, with `choice_trust: 0.5`, `multi_specialist_hold: 0.5`, `shortlist_k: 9` | Phase 167 calibrated on 52 held-out English and Portuguese rows on 2026-10-12. After the loops criteria refinement, both held-out sets score 1.000 in each language, ECE 0.041 and 0.014, zero research-to-companion misses and zero harmful trusts. |
| Complexity | On, with `enabled: true` and `simple_max: 0.40` | Phase 182. Held-out ENABLE in English and Portuguese on 2026-10-16: zero false downgrades in each language, light recall 14 of 14 (EN) and 13 of 14 (PT). The lowest held-out Portuguese `full` row sits between 0.40 and 0.50, so the margin is thinner than on the tuning set |
| Skills | On, with `choice_trust: 0.75`, `needs_skill_hold: 0.6` and `shortlist_k: 5` | Calibrated on 84 English and Portuguese rows on 2026-10-12: zero wrong applies |
| Loop gate | On, with `loop_hold: 0.75` and `resolves_hold: 0.8` | Calibrated 2026-10-12 on 88 tuned and 48 held-out English and Portuguese rows, for all four inflows. On the held-out set, 10 of 10 loops found in each language, precision 1.00, zero false creates. A fence-tolerant Haiku baseline found 9 of 10 (English) and 10 of 10 (Portuguese) with one false create each. The counts are small, so the comparison is coarse. Phase 173 moved conversation to the commitment intake, so this gate now serves email, calendar, and ingestion only |
| Corroboration | Off, with `corroborate_hold: null` and `promote_hold: null` | Calibrated 2026-10-15 (`make calibrate-corroboration`; 84 tuned + 47 held-out English and Portuguese rows). Candidate bars 0.6 and 0.8: English passed on the held-out set (precision 1.00, recall 14 of 14, zero false promotions); Portuguese failed one clause (recall 12 of 13, below the E5 baseline recall minus 0.05). The E5 title-cosine baseline matches every row at 0.75, so its recall is a ceiling, not a rival. The surface stays off until both languages pass; the held-out set is spent for these bars |

Calibration scripts live in `eval/calibration/`. Each one runs the labeled set against the live service and costs credits:

```bash
make calibrate-commitment-intake   # tuned set by default; --set holdout3 gave the 2026-10-16 verdict and is spent; a verdict set is never reused
make calibrate-routing
make calibrate-skills       # add --recall for the offline shortlist check
make calibrate-loop-gate    # tuned set by default; --set holdout gives the verdict
make calibrate-corroboration   # tuned set by default; --set holdout --bars C,P gives the verdict
```

---

## Trace

Judgments appear in the message trace as `JudgmentTrace` rows: the question id, the kind, the latency, the answer, the probabilities, the peakedness, the model, the token count, whether code used the answer (`consumed`), and the skip reason. `embed_route` and `match_skills` add their rows to `state["judgments"]`. The commitment-intake rows are added after the turn. The trace panel in `ze-web` shows them. Use them to see why Ze routed a turn, applied a skill, or kept a fact. A corroboration judgment does not reach the trace: the conversation loop commit is fire-and-forget, so Ze stores the score on the loop's source row and logs `corroboration_judgment` instead.

---

## What System One never does

It never writes replies, drafts, or plans. It never replaces the write confirmation, the confirmation flow, the spend budget, the write-time contradiction check, or any date or window math. A probability of 0.62 does not license Ze to state a suspicion as a fact. Claim kinds on contributions still decide how Ze may surface a claim.

---

## Further reading

- [specs/arch/system-one-models.md](../specs/arch/system-one-models.md) — pinned decisions and the queue of later uses
- [configuration.md](configuration.md#system_one) — keys, bars, and calibration steps
- [skills.md](skills.md#automatic-matching-with-the-system-one-gate) — the skill gate in detail
- [memory.md](memory.md) — fact admission and the commitment intake
- [cognitive-architecture.md](cognitive-architecture.md) — open loops and where the loop gate sits
