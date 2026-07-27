# Data Model: Claim Topology

**Input**: [spec.md](spec.md) Key Entities, [research.md](research.md)

No new tables. This feature adds one shared value-type module and required columns to
existing tables — `correlation_hypothesis` and `memory_facts` (two columns total, per the
original design) plus `memory_signals` (two more columns, added during `/speckit-analyze`
remediation: `Signal`'s two new required fields are persisted to and reconstructed from this
table by `ze_memory/retriever.py::ingest_signal`/`get_signals_by_ids`, which the original
design overlooked). All types are dataclasses per `CLAUDE.md`'s convention (`types.py`, never
`models.py`) — no Pydantic outside `ze_api/api/schemas.py`.

## New module: `core/ze-agents/ze_agents/claims.py`

### `ClaimKind` (StrEnum)

The canonical claim-kind vocabulary, promoted verbatim from `ze_worldstate.types.LoopClaimKind`.

| Value | Meaning |
|---|---|
| `IDENTITY` | who/what something is |
| `FACT` | an observed, corroborable state |
| `INFERENCE` | a derived conclusion — reflection's output, never `FACT` (doctrine rule) |
| `SUSPICION` | a hedged, unconfirmed possibility |
| `PRIORITY` | an attention/ranking claim |

### `Provenance` (StrEnum) — doctrine-closed, exactly four values

The doctrine's epistemic-origin vocabulary — how a claim entered reasoning. Deliberately closed
and small: per `specs/arch/plugin-domain-vocabulary.md`, no plugin-specific or inflow-specific
value may ever be added here (see "Inflow channel" below for that separate concept).

| Value | Meaning |
|---|---|
| `GRAPH_RECALL` | recalled from the memory graph |
| `LIVE_SEARCH` | freshly retrieved via a live search |
| `PROMPT_SUPPLIED` | stated directly by the user in-prompt |
| `SYNTHESIZED` | derived/synthesized, not directly observed |

### `DecayProfile` (StrEnum)

| Value | Matches existing math of |
|---|---|
| `EVIDENCE_WEIGHTED` | `OpenLoop` (`ze_worldstate/decay.py::cascade_from_evidence`) |
| `TIME_LINEAR` | `memory_facts` (`promoter.py::_run_confidence_decay`); reused as-is by `Hypothesis` per clarification |

No `FROZEN` profile — FR-005: "No profile may represent 'confidence that never decays'."

### `Confidence` (dataclass)

| Field | Type | Notes |
|---|---|---|
| `value` | `float` | `[0, 1]` |
| `decay_profile` | `DecayProfile` | discriminates which decay math applies |

### `decay()` function

```
def decay(
    value: float,
    decay_profile: DecayProfile,
    *,
    # EVIDENCE_WEIGHTED params
    remaining_evidence: int | None = None,
    total_evidence: int | None = None,
    # TIME_LINEAR params
    elapsed_days: float | None = None,
) -> float
```

One function, dispatching on `decay_profile`, parameterized rather than duplicated per caller
(FR-004). `EVIDENCE_WEIGHTED` branch: floor `0.05`, `max(floor, value * remaining/total)` or
floor if `total <= 1` — extracted from `ze_worldstate/decay.py` per research.md §5.
`TIME_LINEAR` branch: `max(0.0, value - 0.03)` per elapsed 30-day period, with the caller
(promoter.py, and the new Hypothesis decay job) responsible for the 0.50/0.25 cliff
side-effects on their own row shape (`reviewed`/`contradicted` for `memory_facts`; no cliff
concept exists for `Hypothesis`) — the cliffs are producer-specific consequences of a confidence
crossing a threshold, not part of the shared confidence number itself.

## Inflow channel — not a type in `ze_agents.claims`, a plain string convention

Per `specs/arch/plugin-domain-vocabulary.md`, "which mechanism or plugin produced this claim"
(conversation, email, calendar, ingestion, user-declared, or a future plugin's own value) is
never a closed core enum. It is a plain `str`, owned by whichever core module or plugin
constructs the claim. This feature's only producer that carries this concept is `OpenLoop` (see
below) — `Signal` already has an equivalent plugin-owned string field (`source`), and neither
`Hypothesis` nor `memory_facts` gain one in this feature.

## Retrofitted entities

### `OpenLoop` (`core/ze-worldstate/ze_worldstate/types.py`)

| Field | Was | Becomes | Rule |
|---|---|---|---|
| `claim_kind` | `LoopClaimKind` (own enum) | `LoopClaimKind` (alias of shared `ClaimKind`) | FR-006 — transparent re-export, zero call-site churn |
| `provenance` | `LoopProvenance` (own closed 5-value enum) | `str` | FR-003 — inflow-channel string, no core whitelist |

```python
from ze_agents.claims import ClaimKind

LoopClaimKind = ClaimKind

class LoopProvenance:
    """Plain string-constant namespace, NOT an Enum — see FR-003 / research.md §3.
    Core-owned inflow values only; plugin-owned values (e.g. "email", "calendar")
    are supplied directly by the plugin, never declared here."""
    CONVERSATION = "conversation"
    INGESTION = "ingestion"
    USER_DECLARED = "user_declared"
```

`OpenLoop.provenance: str` (was `LoopProvenance`). Every existing call site using
`LoopProvenance.CONVERSATION` / `LoopProvenance.USER_DECLARED` (production and eleven test
files, per research.md §3's audit) continues to work unchanged, since these are still the exact
same string values, just no longer enum members.

`ze_worldstate/extraction.py::propose_loop_candidates` drops its `prov = LoopProvenance(provenance)`
coercion (which raised `ValueError` for unrecognized strings) and uses the incoming string
directly; its two existing special-case comparisons (`prov == LoopProvenance.CONVERSATION`,
`prov == LoopProvenance.USER_DECLARED`) are unchanged plain string comparisons.

`ze_worldstate/decay.py::cascade_from_evidence` calls `ze_agents.claims.decay(...,
decay_profile=DecayProfile.EVIDENCE_WEIGHTED, ...)` for the confidence arithmetic instead of
its own inline `max(...)` expression (research.md §5); state-transition and logging behavior
unchanged.

### `Hypothesis` (`core/ze-correlation/ze_correlation/types.py`)

New field:

| Field | Type | Rule |
|---|---|---|
| `claim_kind` | `ClaimKind` | `INFERENCE` or `SUSPICION` only — never `FACT` (FR-007) |

No provenance-shaped field added to `Hypothesis` itself in this feature.

### `EvidenceRef` (`core/ze-correlation/ze_correlation/types.py`)

`origin: Literal["graph_recall", "live_search", "prompt_supplied"]` → `origin: Provenance`
(FR-008), gaining `SYNTHESIZED` as a valid value it couldn't previously express. Confirmed
(research.md §4) as the correct, unaffected use of the doctrine-closed enum — this field
describes evidence's epistemic origin, not an inflow channel.

### `memory_facts` row (`core/ze-memory`, `memory_facts` table)

New column: `claim_kind` (see Schema Changes below). Written at fact-write time by the dream
pipeline's existing promotion gate (FR-010): `FACT` for raw/observed rows and corroborated
synthesized rows already promoted; `INFERENCE` for uncorroborated synthesized rows. No
`Provenance`-typed field added — this feature does not touch `memory_facts`' existing
`provenance: str` (`'raw'`/`'synthesized'`) column.

### `Signal` (`core/ze-memory/ze_memory/types.py` — see research.md §1 for the location
correction)

New fields:

| Field | Type | Rule |
|---|---|---|
| `claim_kind` | `ClaimKind` | always `FACT` (FR-012) |
| `confidence` | `float` | required, distinct from existing `magnitude` (relevance) |

`magnitude` is unchanged — still relevance, never renamed/merged (FR-012). No `Provenance`- or
inflow-typed field added — `Signal.source: str` (existing) already identifies the producing
plugin, the same plugin-owned-string pattern `OpenLoop.provenance` now follows too.

**Persistence note (added post-`/speckit-analyze`)**: `Signal` instances round-trip through the
`memory_signals` table (`zm006`) via `ze_memory/retriever.py::ingest_signal` (write) and
`get_signals_by_ids` (read) — a path the original design missed. Since `claim_kind`/`confidence`
are required fields with no default (FR-012 Edge Cases: "required, not optional"), `memory_signals`
needs the same two columns as `correlation_hypothesis`/`memory_facts`, and both call sites need
updating — see Schema Changes below.

## Schema changes (migrations)

Both are required, non-nullable columns with a migration-time backfill — no nullable-and-unset
window (per spec Edge Cases and FR-016).

### `correlation_hypothesis.claim_kind` (`core/ze-correlation`, `zcor` chain)

```sql
ALTER TABLE correlation_hypothesis ADD COLUMN claim_kind TEXT;
UPDATE correlation_hypothesis SET claim_kind = 'inference' WHERE claim_kind IS NULL;
ALTER TABLE correlation_hypothesis ALTER COLUMN claim_kind SET NOT NULL;
```

Backfill value: `'inference'` for every existing row (Assumptions: "no corroboration signal
exists today to distinguish `SUSPICION`").

### `memory_facts.claim_kind` (`core/ze-memory`, `zm` chain)

```sql
ALTER TABLE memory_facts ADD COLUMN claim_kind TEXT;
UPDATE memory_facts SET claim_kind = 'fact'
    WHERE claim_kind IS NULL AND (provenance != 'synthesized' OR corroborated = true);
UPDATE memory_facts SET claim_kind = 'inference'
    WHERE claim_kind IS NULL AND provenance = 'synthesized' AND corroborated = false;
ALTER TABLE memory_facts ALTER COLUMN claim_kind SET NOT NULL;
```

Backfill rule per FR-010 / Assumptions: uses the existing `provenance`/`corroborated` columns
(both already present as of `zm009`) to classify every existing row.

### `memory_signals.claim_kind` / `memory_signals.confidence` (`core/ze-memory`, `zm` chain — added post-`/speckit-analyze`)

```sql
ALTER TABLE memory_signals ADD COLUMN claim_kind TEXT;
UPDATE memory_signals SET claim_kind = 'fact' WHERE claim_kind IS NULL;
ALTER TABLE memory_signals ALTER COLUMN claim_kind SET NOT NULL;

ALTER TABLE memory_signals ADD COLUMN confidence DOUBLE PRECISION;
UPDATE memory_signals SET confidence = 1.0 WHERE confidence IS NULL;
ALTER TABLE memory_signals ALTER COLUMN confidence SET NOT NULL;
```

Backfill values: `claim_kind = 'fact'` for every existing row (every signal ever emitted was
perception, per FR-012's "always `FACT`" rule — no ambiguity, unlike the other two tables).
`confidence = 1.0` for every existing row — a documented default since no confidence concept
existed for signals before this feature; flagged here for spec-author confirmation rather than
silently assumed, since unlike the `claim_kind` backfill, no existing signal data expresses a
notion of confidence to derive this value from.

No schema change to `open_loops.provenance` — it stays a `TEXT` column at the database level
(only its Python type annotation changes from `LoopProvenance` to `str`); no migration needed.

## New module: `core/ze-proactive`'s staleness helper

`core/ze-proactive/ze_proactive/staleness.py` (new file):

```python
def is_stale(timestamp: datetime, window_days: int, *, now: datetime | None = None) -> bool
```

Pure function: `cutoff = (now or datetime.now(UTC)) - timedelta(days=window_days); return
timestamp <= cutoff`. Mirrors `stale_suspicion.py`'s existing inline shape exactly (FR-015).
Callers retain their own state-transition and window-configuration logic — this function only
answers "is this past its cutoff."

## Entity relationship summary

No new relationships. `ClaimKind`/`Provenance`/`Confidence`/`DecayProfile` are value types with
no identity of their own — they are always fields on one of the four existing producer types,
never persisted or queried independently. The inflow-channel string is likewise never persisted
or queried as its own entity — it's a plain column value on `OpenLoop`.
</content>
