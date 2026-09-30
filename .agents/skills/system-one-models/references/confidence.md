# Confidence — Reference

> How System One models report certainty and how to use it architecturally.

## What confidence is

Confidence is a statistic computed from the probability distribution. It measures how peaked the distribution is:
- **1.0:** All probability on one option/level.
- **Near 0:** Evenly spread across all options/levels.

Confidence is **not** an independent judgment of correctness. It describes the distribution's shape.

## Noul has no separate confidence

A Noul's distribution has only two outcomes (yes/no). The single `noul` value describes it completely — no summary statistic needed.

## Three paths for using confidence

| Range | Behavior | Example |
|-------|----------|---------|
| High (~0.8+) | Act automatically | Route to department, show result |
| Medium (~0.4–0.8) | Proceed with caution | Ask user to confirm, flag for review |
| Low (~<0.4) | Do not act | Route to human, request clarification, fall back |

## Thresholds scale with risk

Different actions in the same system should have different confidence thresholds:

- **Read-only action** (show balance): 0.6 confidence is fine.
- **Destructive action** (approve transfer): 0.85+ to act automatically; otherwise ask user to confirm.
- **Low-confidence floor** (<0.5): Always route to human regardless of action.

## Common pitfalls

- **Low confidence on a harmless preference** (e.g., which color scheme) is fine. Several options may all be acceptable; don't escalate.
- **A Noul near 0.5** means yes/no are equally probable, NOT medium intensity. Use Score for degree.
- **Ignore uncertainty on unused branches.** A speculative question with a split distribution doesn't matter if code never reads it.
- **Distribution shape matters.** Two different distributions can produce the same score. Read `probabilities` alongside `score`.
- **Confidence is not a correctness check for the broader workflow** — only the individual judgment. Route to human review rather than trying to fix low confidence by tweaking the question.
