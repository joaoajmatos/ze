# Research: Loop Extraction Gate

Evidence from the code at `main` ed5063fa unless noted.

## R1 — What the gate decides today
`_run_extraction_gate` (extraction.py:87) returns five fields. `propose_loop_candidates` branches: `resolves_existing` (close a match), `not is_loop or not title` (nothing), `explicit_declaration` (active 0.9, `user_declared`), else matching then `suspected` 0.3. Window: `implied_window_days` → `compute_drift_deadline` (drift.py:14), default 7.
**Decision**: three Nouls cover `is_loop`, `explicit_declaration`, `resolves_existing`. The title and window stay model-written because System One cannot write text and no code date parser exists.

## R2 — Offline baseline
No Haiku gate output is stored anywhere (no persisted gate result, zero `loop_extraction` log lines, June-era eval results, empty local `open_loops`). The repo has 6 `gold_act=loop` rows in `speech_act.jsonl` and nothing else labeled.
**Decision**: the calibration script measures Haiku and System One side by side (FR-017). That baseline is what FR-018 compares against.

## R3 — Where the conversation gate runs
The hook runs via `fire_and_forget` after the trace update (nodes/memory.py:164), so it cannot add rows. `fact_extractor` is awaited at L89 and 163 appends rows via `judged_trace`.
**Decision**: await the gate in the node beside `fact_extractor`; commit stays fire-and-forget. The node duck-types the admission; `ze_core` does not import `ze_worldstate`.

## R4 — Concurrency
The 163 request and the loop gate request are independent. **Decision**: `asyncio.gather` them in the node so the added latency is the slower one, not the sum. Exceptions are contained per call (fail open).

## R5 — Trace merge
Both calls produce rows. **Decision**: collect rows from both into one list and do a single `dataclasses.replace(trace, judgments=[*trace.judgments, *rows])`. Append-only, never replacing `embed_route` or 163 rows.

## R6 — Trivial-turn skip
`is_trivial_turn` (extractor.py:120, regex) is already the 163 skip. **Decision**: reuse it for the conversation gate, before both the System One and Haiku paths. Non-conversation text has no equivalent and is only skipped when empty.

## R7 — Per-provenance state and caps
Inputs differ: conversation `ctx.prompt`; email full `msg.body` (processor.py:157); calendar `"{title}. {summary}"` (calendar_reminder.py:61); ingestion facts joined by ". " (sink.py:67).
**Decision (plan-time, tunable only on the tuned set)**: named constants in `loop_judge.py`: conversation 1000 chars, email 1500 (head), calendar 600, ingestion 1500. State is a dict with one named key per shape (`user`, `email`, `event`, `facts`) plus `source`. The title writer sees the same capped text.

## R8 — Explicit declaration narrowing
The 109 gate honors a model-returned `explicit_declaration` for any provenance, so a third party's email can create an `active` 0.9 loop. **Decision**: on the System One path `explicit_declaration` is only asked for conversation. The Haiku fallback keeps the 109 behavior; the asymmetry is recorded, not shimmed.

## R9 — Both resolves and concern positive
109 defines resolves as "is_loop false". **Decision**: resolve wins; the concern Noul is recorded `consumed: false`.

## R10 — Noul wording (draft, tuned only on the tuned set)
- `is_open_concern`: "Does this text imply something the user, or someone in their life, still has to do, decide or follow up on, that is not yet done?" plus a state note about the source. Negatives named in the instruction: questions, small talk, notifications, marketing deadlines, routine events, reference facts.
- `explicit_declaration`: "Is the user themselves stating that they have to, need to, or want to be reminded to do this?" Conversation only.
- `resolves_existing`: "Does the text report that something the user needed to do is now done?"

## R11 — Calibration scoring
- create = decision in {create_declared, create_suspected}; positive row = `gold_loop` true.
- precision = correct creates / creates; recall = created positives / positives.
- false create = a create on a row with `gold_loop` false (resolves rows included).
- Reported but not gating: false resolve (resolve on a row with `gold_resolves` false), false declared (declared on `gold_explicit` false), explicit and resolves accuracy.
- Haiku baseline: `is_loop and title` → create; `explicit_declaration` → declared; `resolves_existing` → resolve.
- 163 agreement log: on conversation rows run `SPEECH_ACT_QUESTIONS` (user text, empty assistant) and count `act == loop` vs the gate's create decision.
- Verdict per language on the held-out set; failing clause printed.

## R12 — Eval
Eval threads skip write-side effects (nodes/memory.py `is_eval`), so a chat eval scenario cannot observe loop creation. No scenario is added; coverage is unit tests plus live calibration.

## R13 — graphify blast radius
`propose_loop_candidates`: `_propose`, `conversation_memory_hook`, `test_extraction.py` (9 tests), `test_contribution.py:109`. `_run_extraction_gate`: only `propose_loop_candidates`. `make_loop_extractor_from_parts`: `build_container` (container.py:596), `make_loop_extractor` (:833), `app.py` lifespan, `from_config` (:380), ze-seed `_apply`. `OpenLoop` is not touched. The implementer re-runs `graphify affected` before each signature change.

## R14 — Calibration result (2026-10-12)

Live runs: `make calibrate-loop-gate` (System One `typesafe/jev-1.13`, Haiku `anthropic/claude-haiku-4-5`).

**Finding: the 109 gate is inert against Haiku 4.5.** `_run_extraction_gate` calls `json.loads(raw)` and
Haiku wraps every reply in a ```json fence even with `response_format` set, so all 136 calibration replies
failed to parse (88/88 tuned, 48/48 held-out); the gate returned `None` each time. Production has therefore
created no loops through the gate. It also explains R2 (zero `loop_extraction` lines, empty `open_loops`).
The gate was left byte-for-byte per FR-013; the title writer added in this phase strips the fence. The
calibration compares against a fence-tolerant copy of the same prompt ("Haiku tol"), the stronger baseline.
A follow-up should fix the fallback's parse (one line) or hard-cut the fallback.

**Tuned set (88 rows; wording tuned here only).** Final wording, bars `loop_hold 0.75`, `explicit_hold 0.85`,
`resolves_hold 0.8`: 32/32 positives created, 0 false creates, 0 false declared, explicit accuracy 1.00, resolves
accuracy 1.00. Haiku (fence-tolerant): recall 32/32, 2 false creates, 7 false declared, precision 0.941.
Safe plateaus: `loop_hold` 0.70 to 0.80 (0 false creates, recall 1.00), `resolves_hold` any 0.65 to 0.95. Noul
separation: concern negatives top out at 0.70, positives start at 0.80; explicit negatives at 0.70, positives at
0.89. Two ambiguous tuned rows (`t-en-005`, `t-pt-005`) were made unambiguous after the first runs; wording of
`is_open_concern` and `explicit_declaration` was revised once (explicit accuracy 0.875 to 1.00, recall 0.906 to 1.00).
163 speech-act `loop` agreed with the gate on 26/32 conversation rows (logged only).

**Held-out run (one run, wording and bars frozen in c750dd01, file `loop_gate_holdout.jsonl` untouched):**

```
HELD-OUT VERDICT   bars: loop_hold=0.75 explicit_hold=0.85 resolves_hold=0.8
[en] ENABLE  system one: P=1.000 R=1.000 (10/10) creates=10 falseCreates=0 fallback=0 | haiku(tol): P=0.900 R=0.900 (9/10) creates=10 falseCreates=1
[pt] ENABLE  system one: P=1.000 R=1.000 (10/10) creates=10 falseCreates=0 fallback=0 | haiku(tol): P=0.909 R=1.000 (10/10) creates=11 falseCreates=1
OVERALL: ENABLE
production 109 gate as-is: 48/48 replies unparseable (R=0/20, no creates)
```

Not gating: PT had 1 false resolve (a resolve on a row not gold-resolving); false declared 0 for System One vs 3
for Haiku; explicit accuracy 1.00 vs 0.92. Counts are small (10 positives per language): the comparison is coarse.
Outcome: `system_one.surfaces.loop_gate` ships enabled with the bars above (`apps/ze-api/config/config.yaml`).
