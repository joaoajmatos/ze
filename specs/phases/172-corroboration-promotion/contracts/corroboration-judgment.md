# Contract: Corroboration judgment and effects

## Flow (one gate-admitted text, one matched loop)

```
gate decision create_suspected | create_declared  (168 System One path or 109 Haiku fallback)
  → Haiku title → find_matching_loop(states=suspected,active,drifting) → existing
  → existing.state != suspected  → 170 behavior (link; record_corroboration if active)   [unchanged]
  → existing.state == suspected:
       dropped = matching dropped loop (already looked up for the fingerprint check)
       independent, reason = is_independent(key, new_evidence,
                                            list_sources(existing), list_evidence(existing),
                                            list_sources(dropped) if dropped else [])
       not independent → 170 behavior; log corroboration_skipped(reason)            [no request]
       independent     → decision = judge(existing.title, text, inflow)            [≤1 request]
            fallback | not_same → 170 behavior; log corroboration_judgment
            corroborate         → link evidence+entities
                                  row = add_source(corroboration, promoted=false, score, model, latency)
                                  row is None → stop (key raced in), log reason=duplicate_source
                                  set_confidence(min(0.6, 1-(1-c)(1-0.5·s)))
            promote             → as corroborate, then
                                  loop = promote(id, confidence=0.7, window_days=7)
                                  loop is not None → mark_source_promoted(row.id)
                                  log corroboration_judgment(outcome=promote|corroborate)
```

On creation of any loop with a key (suspected or declared path): `add_source(origin, key, evidence=first evidence ref or None)`.

## Independence (pure)

| Check, in order | Reason when it fails |
|---|---|
| key is not `None` and `key.ref` is non-empty | `no_key` |
| key not in `{s.key for s in loop_sources}` | `same_source` |
| no ref in `new_evidence` is in `loop_evidence` | `same_evidence` |
| key not in `{s.key for s in dropped_sources}` | `dropped_source` |
| — | `independent` |

## Question and state

| Field | Value |
|---|---|
| id | `same_concern` |
| type | `noul` |
| instructions | research R4 wording (tunable on the tuned set only) |
| state | `{"loop": title[:200], "source": inflow, <168 key>: capped text}` |
| attempts | `max_attempts=1` |

## Decision table (`decide(result, cfg)`, pure, never raises)

| # | Condition | Kind | Reason |
|---|---|---|---|
| 1 | `cfg.enabled` false | fallback | `disabled` (no request is made; checked before calling) |
| 2 | a bar null, invalid, or `corroborate_hold > promote_hold` | fallback | `uncalibrated` (warning; no request) |
| 3 | client missing | fallback | `unavailable` |
| 4 | `result.outcome == "skip"` or exception | fallback | skip reason or `error` |
| 5 | answer missing, not a Noul, NaN, outside [0, 1] | fallback | `invalid_answer` |
| 6 | `s >= promote_hold` | promote | `same_concern` |
| 7 | `s >= corroborate_hold` | corroborate | `same_concern` |
| 8 | otherwise | not_same | `below_bar` |

## Config

```yaml
system_one:
  surfaces:
    corroboration:
      enabled: false
      corroborate_hold: null
      promote_hold: null
```

Parsed by `corroboration_surface_config(settings)` with the same tolerant reader as `loop_gate_surface_config`.

## Invariants

- No System One request unless the match is `suspected`, independent and the surface is calibrated.
- Promotion never changes `provenance`, `claim_kind`, `title`, evidence or entity links; never writes a fact; never uses the contribution seam.
- `closed` and `dropped` loops are never judged.
- Every exception inside `corroborate_match` is caught, logged as `corroboration_failed`, and the 170 behavior result is returned.
