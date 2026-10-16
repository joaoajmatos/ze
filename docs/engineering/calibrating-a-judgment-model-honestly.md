# Calibrating a judgment model honestly

A gate is only as good as the data it never saw.

Ze uses a small model, System One, for closed questions. It never writes text. It returns a choice among labels, a yes/no probability, or a score. Code reads the answer, compares it with a bar, and decides. Five parts of Ze use it: the commitment intake (facts and loops from conversation), routing, skill matching, the open-loop gate for email, calendar, and ingestion, and loop corroboration. See [System One](../system-one.md) for the design.

This post is about the bars. A bar is the number that says "trust this answer." Picking a bar is easy. Picking one you can defend is the work. Ze's record has five lessons, and several of them are failures.

## The rules

Every System One surface follows the same rules, written in [specs/arch/system-one-models.md](../../specs/arch/system-one-models.md):

- The surface ships off with null bars. A null bar means "uncalibrated," and an uncalibrated surface skips.
- A labeled set tunes the wording and the bars. A second, held-out set judges them once. Nobody tunes against the held-out set.
- The calibration runs live and costs credits, so a person starts it. The test suite never calls the model.
- A skip, a timeout, or a malformed answer sends Ze down the old path. System One never blocks a turn.
- Rows come in English and Portuguese, and each language gets its own verdict.

These rules cost time. The next four stories show what they bought.

## Lesson 1: a confident model can be wrong

Phase 164 added a routing Choice. E5 embeddings shortlist the agents, and System One picks one. The phase shipped with the surface off.

The reason sits in the [167 spec](../../specs/phases/167-routing-choice-criteria/spec.md): on a held-out set, the Choice was about 0.98 confident while 80% right. A bar on confidence could not separate the right answers from the wrong ones.

Phase 167 found three causes:

1. **Contradictory descriptions.** The companion and research agents both claimed "explain X." The Choice reads agent descriptions as its criteria, so it could send an explanation to the agent that cannot search the web.
2. **Bare question wording.** "Which one agent?" gave the model little to go on, and the `none` option was one weak sentence.
3. **A weak shortlist.** E5 scores on this roster are flat, between 0.76 and 0.82. On a fresh set, the right agent sat outside the top six for 43% of rows. Offline recall at a shortlist size of 6 was 0.571. No wording can pick an agent the model never sees.

The fixes were plain. Each agent got `routing_criteria`, a use-for and not-for text written for the Choice. The `none` criterion got stronger. The shortlist grew until offline recall passed 0.95, which took a size of 9 on a roster of 10. At that size E5 filters almost nothing for the Choice. The spec says so, and the pinned rule about E5 now says so too.

## Lesson 2: report the miss, and change the rule in writing

Phase 167 also wrote a fresh held-out set, 30 rows in two languages, that the implementer never saw. The first acceptance rule was strict: at least 0.95 accuracy per language on both sets, calibration error at most 0.10, and zero cases where research work went to companion.

The live run at a shortlist size of 9 passed almost everything:

| Set | English | Portuguese | Calibration error |
|---|---|---|---|
| Tuned | 23 of 23 | 22 of 23 | 0.053 |
| Held-out 1 | 9 of 10 | 10 of 10 | 0.080 |
| Held-out 2 | 14 of 14 | 14 of 14 | 0.013 |

It had zero research-to-companion misses and zero harmful trusts at every bar. The script still printed FAIL for one line: English accuracy on the first held-out set was 0.90, below 0.95. A loops question had gone to companion, at a confidence of 0.29.

The spec did not hide this and did not move the bar quietly. It added a dated clarification. The one miss sits below the trust bar of 0.5, so Ze never acts on it. It falls back to the old decompose path, which is today's behavior. The acceptance rule changed to what actually protects the user: zero harmful trusts, calibration error at most 0.10, zero research-to-companion misses. Raw accuracy stays in the report but does not gate. The user approved the amendment, and the script's FAIL line stays in the record with a note that it is expected.

The complexity score fared worse. It overlapped across levels, so its bar stays unset, and the word-count classifier still picks the model tier.

## Lesson 3: the baseline you skip can be broken

Phase 168 replaced a Haiku call that decided whether text opens, declares, or resolves an open loop. The calibration compared System One with that gate.

The comparison found a bug. The old gate called `json.loads` on the model's reply. Haiku wrapped every reply in a markdown fence, so every one of the 136 calibration replies (88 tuned, 48 held-out) failed to parse. The gate returned nothing each time. The research note says the production gate had created no loops, which also explained an empty `open_loops` table that an earlier note had flagged.

The team measured against a copy of the old gate that strips the fence, because a fair baseline matters more than an easy win. Then they fixed the real gate. The same day, one commit replaced the ad-hoc fence handling and bare `json.loads` calls at every model-reply site with one tolerant helper, `parse_llm_json`. The code guide now says to parse every model reply that way.

The held-out verdict, from one run with the wording and bars frozen in an earlier commit:

| Language | System One | Haiku (fence-tolerant) |
|---|---|---|
| English | 10 of 10 loops found, 0 false creates | 9 of 10, 1 false create |
| Portuguese | 10 of 10, 0 false creates | 10 of 10, 1 false create |

The note adds a caveat: ten positives per language is a small set, so the comparison is coarse. The surface shipped on.

## Lesson 4: ship it off when the evidence says so

Phase 172 lets an independent source raise or promote a suspected loop. One System One question asks whether the new text is about the same matter as the loop. Code decides independence, so the model never does.

The tuned set was clean. No false promotions at any bar. Bars of 0.6 to corroborate and 0.8 to promote came from that set alone, chosen before the held-out run.

The held-out run (24 English rows, 23 Portuguese rows) gave:

| Language | Positives found | Precision | Recall | False promotions | Verdict |
|---|---|---|---|---|---|
| English | 14 of 14 | 1.00 | 1.00 | 0 | ENABLE |
| Portuguese | 12 of 13 | 1.00 | 0.923 | 0 | KEEP OFF |

Portuguese failed one clause. Recall must stay within 0.05 of the E5 baseline, and that baseline matches every row, so recall 0.923 fell short of 0.95. The rule says the surface turns on only when both languages pass. So it stays off, with null bars.

The research note lists what could change the verdict: a larger held-out set, an absolute recall floor, or a lower corroborate bar. It also records that none of these was applied, and that the held-out file is spent for these bars and this wording. Any change needs new data first.

Two details stand out. The English result alone would have justified shipping, and the rule still held. And one row out of 13 decided the Portuguese verdict, which is a fair reason to say the clause is brittle, in the note, without bending it.

## Lesson 5: a spent set stays spent

Phase 173 merged two judgments of the same message into one request. The calibration followed the same rules. It took three held-out sets.

The first set (120 rows) returned `KEEP OFF`. In both languages one deadline task created a loop where the label said goal. English loop recall was 0.875, below the 0.888 floor. Portuguese Choice accuracy was 0.88, below 0.90. The team fixed the wording from the tuned set only, because the first set was now spent.

A second set, written blind, gave English `ENABLE` and Portuguese `KEEP OFF`. Portuguese Choice accuracy was 0.892, nine wrong answers in 83 rows. Eight wrong would have passed. Three of the nine were "resolves" rows, where the correct label has no choice to match.

The second set also showed a defect that no clause measured. In each language, "I sent my CV and I'm waiting for her reply" resolved an open loop. The model read the message as `waiting_on` at 1.00, and the resolves question still fired. No clause covered it. The team amended the rules in writing, with dates, and each amendment came before the run it governed. Before the second run, false resolves could not exceed the baseline's. Before the third, Choice accuracy left out resolves rows, and rows where the user is waiting on someone had to write nothing. They fixed the wording, then wrote a third set with a new author who saw only a written brief.

The third set (147 rows) ran once at bars frozen on the tuned set. It returned `ENABLE` in both languages. Per language there were zero duplicate bookings against 5 and 3 for the old pipeline, zero false creates against 3 and 3, and loop precision 1.00 against 0.73 and 0.79. The shipped config turned on after that run, with the frozen bars.

The record shows two failed verdicts and no re-scoring. Each time, the set that failed was retired, and only a set nobody had tuned against could change the answer.

## What to take from this

- Ship every judgment surface off, with null bars, and make "uncalibrated" a state the code understands.
- Keep a held-out set that nobody tunes against, and run it once per set of bars.
- Report the failing line. When you change a rule, change it in writing, with a date and a reason.
- Retire a held-out set after its verdict, pass or fail. A new verdict needs a new set.
- Compare against a baseline that works. A broken baseline flatters the new model.
- Give each language its own verdict. An average hides the language that failed.
- Let code own the decision. A probability of 0.62 does not license Ze to state a suspicion as a fact.

The calibration scripts and labeled sets live in [`eval/calibration/`](../../eval/calibration/). The full results are in the research notes of phases [164](../../specs/phases/164-routing-choice-after-e5/spec.md), [167](../../specs/phases/167-routing-choice-criteria/spec.md), [168](../../specs/phases/168-loop-extraction-gate/research.md), [172](../../specs/phases/172-corroboration-promotion/research.md), and [173](../../specs/phases/173-commitment-intake/research.md).
