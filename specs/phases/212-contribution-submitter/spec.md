# Feature Specification: Contribution Submitter

**Feature Branch**: `212-contribution-submitter`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 201 (typed turn services and core stack contributions, so the submitter has one wiring home) and 203 (the open-loop lifecycle owns the loop producers' writes). Builds on 199's narrowed Executive licence (`executive-licence.md`).

**Input**: Architecture review 2026-10-22, candidate C8: "One ContributionSubmitter built in ze-api wiring, holding an evidence resolver over memory, the collision store and NLI; injected into the 12 producers; the per-producer existence checkers deleted; strict evidence checks uniform; the module-level mutable `_window` in `ze_collision/detect.py` removed. The contribution-seam ADR keeps ze-plugin free of ze-memory."

## Context

Every change to the world-state goes through the contribution seam. That means `validate_and_submit` (`ze_plugin/contribution.py:89-199`), usually wrapped by `submit_and_detect_collisions` (`ze_collision/detect.py:150-193`).

Validation itself is deep: licensing, action and feedback payload rules, required evidence, dangling evidence. But each producer has to bring what validation needs.

**The existence checkers.** `validate_and_submit` takes four optional checkers, one each for facts, episodes, signals and action records. It treats a missing checker as "the evidence does not exist" and rejects the contribution. The exception is the kinds in `_SKIP_DANGLING_WITHOUT_CHECKER` (`ingestion`, `goal`; `contribution.py:76`, `:185-197`). Five producers write their own checkers:

| Producer | Checkers |
|---|---|
| `ze_worldstate/extraction.py:217-230` | fact and episode, through `memory_store.get_facts_by_ids` and `get_episodes_by_ids`, which are not on the `MemoryStore` protocol (`ze_memory/store.py:54`) |
| `ze_correlation/engine.py:288-298` | fact, episode, signal |
| `ze_memory/dream/dream_pass.py:467-479` | fact and episode, in raw SQL |
| `ze_personal/graph/memory_hooks.py:188-195` | episode, signal |
| `ze_personal/jobs/social_cooccurrence.py:149-156` | episode, signal |

The others pass no checkers. Whether the dangling-evidence check is strict, or never runs, therefore depends on what each producer wired up. `tracking.py:135` passes none.

**Collision wiring.** `submit_and_detect_collisions` runs the collision check only when both `collision_store` and `nli_client` are passed ("not every call site is wired yet", `detect.py:157-160`). Both are threaded through each producer's constructor or call:

- `ze_memory/contribution.py:110-111` reads them off the memory store's private attributes with `getattr(store, "_collision_store")`;
- `retriever.py:1323-1324` does the same.

**The recency window.** The collision recency window is a module-level mutable list (`detect.py:47`). Its comment calls it single-process cache state, but it breaks the AGENTS.md rule against module-level mutable state, and it is shared across tests.

### Blast radius

`graphify affected submit_and_detect_collisions --depth 1` reaches 12 production call sites in 9 modules:

- `ze_priority/service.py:63`
- `ze_correlation/engine.py:276`
- `ze_memory/contribution.py:105`
- `ze_memory/dream/dream_pass.py:519`
- `ze_memory/retriever.py:1318`
- `ze_worldstate/extraction.py:363`, `:470`
- `ze_worldstate/tracking.py:135`
- `ze_personal/contacts/consolidator.py:249`, `:277`
- `ze_personal/graph/memory_hooks.py:196`, `:230`
- `ze_personal/jobs/social_cooccurrence.py:208`

It is also re-exported by `ze_sdk/contribution.py`.

`validate_and_submit` is called directly by `ze_memory/action_records/contribution.py:51` and `ze_memory/feedback_records/contribution.py:53`. Those two never get collision detection.

The loop producers (`extraction.py`, `tracking.py`) are reshaped by 203. This phase injects the submitter into 203's lifecycle module rather than into the old free functions.

### What does not change

`contribution-seam.md` keeps ze-plugin free of ze-memory, which is why evidence checks are callables today. That holds:

- the submitter's interface lives in ze-plugin;
- its adapter (the evidence resolver over memory, the collision store, NLI) is built in ze-api wiring, which may see every package.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - No claim cites evidence that does not exist (Priority: P1)

A hypothesis, a suspected loop or a contact proposal cites an episode that was deleted (for example by forget, or by a data reset). Ze refuses the contribution, whichever function produced it, and logs the refusal. Today it depends on whether that producer wrote a checker for that evidence kind.

**Why this priority**: The doctrine says inferences and suspicions must cite real evidence. A citation to a missing record is a claim with no grounds.

**Independent Test**: For each producer, submit a contribution citing a missing fact, episode, signal and action record. Every one is rejected with `DanglingEvidenceError`, and each existing one is accepted.

**Acceptance Scenarios**:

1. **Given** a correlation hypothesis citing a deleted episode, **When** it is submitted, **Then** it is rejected, exactly as a dream artifact citing the same episode is rejected.
2. **Given** `track_loop` creating a declared loop with conversation evidence, **When** the episode exists, **Then** the loop is created. **When** it does not, **Then** the loop is refused with a typed error.
3. **Given** evidence of kind `ingestion` or `goal`, **When** it is submitted, **Then** it is checked against its own store. If the resolver does not cover that kind, the behaviour is stated (see FR-004).

---

### User Story 2 - Every contribution is checked for collisions (Priority: P2)

Two functions disagree about the same face. For example, the user's priority override and Executive's ranking, or a contact proposal and a reflection inference about the same person. The disagreement is logged, whichever producer submitted second. Today a producer that was not passed the collision store and the NLI client is silently skipped.

**Why this priority**: Collision logging (phase 126) is the only record of cross-function disagreement. Where it silently does nothing, governance cannot see the disagreement.

**Independent Test**: Every producer, submitting a contradicting contribution after a seeded one, writes a collision row. Action and feedback records are excluded by rule, not by omission (see FR-007).

**Acceptance Scenarios**:

1. **Given** a perception fact and a contradicting dream artifact on the same entity within 24 hours, **When** the second is submitted, **Then** a collision row is written.
2. **Given** the tests run in one process, **When** two tests submit contributions, **Then** neither sees the other's recency window.

---

### User Story 3 - A producer supplies only its contribution (Priority: P3)

A maintainer adds a new producer. It receives the submitter as an injected dependency and calls it with the contribution, the write, the result id and the producer kind. It never builds checkers, and it never threads a collision store or an NLI client.

**Why this priority**: This is the leverage. Five copies of the checkers, and the collision plumbing through about ten constructors, are deleted.

**Independent Test**: Each producer's tests use one fake submitter, and no producer constructor takes `collision_store` or `nli_client`.

**Acceptance Scenarios**:

1. **Given** a new producer test, **When** it is given a fake submitter, **Then** it can assert exactly what was submitted, with no store fakes.

---

### Edge Cases

- **The submitter is built before the memory store** (wiring order). The evidence resolver must not need the fully built memory store at construction. It reads evidence through the pool, or is handed a narrow evidence-lookup interface.
- **The NLI client is unavailable** (local model not loaded). Collision detection degrades with one logged warning per process, never silently per call, and the write still succeeds.
- **The collision check fails or times out.** It stays fire-and-forget after the write, as today. The write's result is never affected.
- **A contribution with no evidence where none is required** (facts, priorities). It is accepted as today.
- **Tests that need a clean recency window.** They build a fresh submitter.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: One contribution submitter MUST exist.
  - Its interface (submit a contribution with its write, result id and producer kind; return the write's result) lives in ze-plugin next to `validate_and_submit`.
  - Plugins reach it through `ze_sdk`.
- **FR-002**: The submitter's adapter MUST be built once in ze-api wiring. It holds:
  - an evidence resolver covering facts, episodes, signals and action records;
  - the collision store;
  - the NLI client.
- **FR-003**: Every producer listed in the blast radius MUST receive the submitter as an injected dependency, and call it in place of `submit_and_detect_collisions`. That covers the 12 call sites, or their 203 successors, and the action and feedback record submitters.
- **FR-004**: The dangling-evidence check MUST be uniform. Every evidence kind is either checked by the resolver or listed in one documented set of kinds that the resolver does not check.
  - A producer can never switch the check off by omission.
  - `_SKIP_DANGLING_WITHOUT_CHECKER` is replaced by that one list.
- **FR-005**: The five per-producer existence checkers MUST be deleted, and so must the `getattr(store, "_collision_store")` and `getattr(store, "_nli")` reads.
- **FR-006**: The memory store's protocol MUST declare the evidence lookups that callers use (by fact ids, by episode ids), or the resolver MUST read them without going through the protocol. In either case no caller relies on methods the protocol does not declare.
- **FR-007**: Collision detection MUST run for every contribution unless its claim kind is excluded by a stated rule. Action records and feedback records are evidence, not claims: either they are checked, or the exclusion is documented in the seam ADR.
- **FR-008**: The recency window MUST belong to the submitter instance, not to the module. One instance per process in production; a fresh instance per test.
- **FR-009**: Licensing, the payload rules and required-evidence validation MUST behave exactly as today, including the narrowed Executive licence from 199.
- **FR-010**: `submit_and_detect_collisions` and the checker parameters of `validate_and_submit` MUST be removed from the public surface (`ze_collision`, `ze_sdk`), as a pre-v1 hard cut. `validate_and_submit` stays as the validation step inside the submitter.

### Key Entities

- **Contribution**: a function's typed proposal to change the world-state (glossary).
- **Contribution submitter**: the one entry point through which every producer submits a contribution. It validates, writes, then checks for collisions.
- **Evidence resolver**: answers "does this cited record exist?" for every evidence kind the seam knows.
- **Collision**: two contributions from different functions that disagree about the same face.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of producers reject a contribution citing missing evidence of any checked kind. Today it depends on the producer.
- **SC-002**: 100% of claim-kind producers are covered by collision detection. Today the coverage depends on wiring.
- **SC-003**: Zero producer constructors or call sites take `collision_store`, `nli_client` or `check_*_exists`. Today about ten constructors and 12 call sites do.
- **SC-004**: Zero module-level mutable state in `ze_collision`.
- **SC-005**: All existing contribution, collision and producer tests pass after changing construction only, with no changes to expected outcomes.

## Assumptions

- **Wiring home.** 201 gives core packages a uniform way to contribute services, so the submitter is built once and reaches every core stack and plugin without new hand lists in `container.py`.
- **Loop producers.** 203's lifecycle module is the loop producer. This phase wires the submitter into it, not into `extraction.py`'s free functions.
- **Ingestion and goal evidence.** Whether the resolver also checks `ingestion` and `goal` evidence is decided in planning. Either way, the rule is stated in one place (FR-004).
- **No migration.** No new tables. Collision rows keep their schema.
- **Pre-v1 hard cut** (constitution Principle VIII).
