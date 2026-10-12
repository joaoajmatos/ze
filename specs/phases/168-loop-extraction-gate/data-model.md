# Data Model: Loop Extraction Gate

No database change.

## LoopGateSurfaceConfig (frozen dataclass, `loop_judge.py`)
`enabled: bool = False`, `loop_hold`, `explicit_hold`, `resolves_hold`: `float | None`. `calibrated` = enabled and all three set. Invalid bar values (bool, non-number, NaN, outside 0..1) become `None` with a warning.

## LoopGateDecision (frozen)
`kind`: `resolve` | `create_declared` | `create_suspected` | `hold` | `fallback`; `reason: str`; `consumed: frozenset[str]`.

## LoopAdmission (dataclass, `admission.py`)
`decision`, `judgment: SystemOneResult | None`, `question_ids: tuple[str, ...]`, `question_kinds: dict[str, str]` (all `noul`), `consumed: frozenset[str]`, `skip_reason: str | None`, `commit: Callable[[], Awaitable[list[OpenLoop]]] | None`. The node reads these by attribute; it never imports the type.

## TitleWriterResult
`title: str`, `implied_window_days: int | None`. The window is a positive whole number or `None`.

## State shapes (dict sent as System One state)
- conversation `{"source": "conversation", "user": <<=1000 chars>}`
- email `{"source": "email", "email": <<=1500 chars>}`
- calendar `{"source": "calendar", "event": <<=600 chars>}`
- ingestion `{"source": "ingestion", "facts": <<=1500 chars>}`

## Calibration row (JSONL)
`id`, `lang` (`en`|`pt`), `provenance` (`conversation`|`email`|`calendar`|`ingestion`), `text`, `gold_loop`, `gold_explicit`, `gold_resolves`, `kind`. Invariants: `gold_explicit` implies `gold_loop` and provenance `conversation`; `gold_resolves` implies not `gold_loop`.

## Config
```yaml
system_one:
  surfaces:
    loop_gate:
      enabled: false
      loop_hold: null
      explicit_hold: null
      resolves_hold: null
```
