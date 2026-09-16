# Quickstart: Validate the Procedure Lifecycle

## Prerequisites

- Phase 137 evidence/learning contracts are implemented and importable.
- The procedure lifecycle migration is applied to a disposable pre-v1 database.
- Existing goal, workflow, workspace, dream, and skills test fixtures are available.

## Hard-cut check

Before implementation verification, search production paths:

```bash
rg "propose_procedure\\(" --glob '*.py' core plugins apps -g '!**/tests/**'
rg "INSERT INTO memory_procedures" --glob '*.py' core plugins apps -g '!**/tests/**'
```

Expected result after the phase: no public writer call and no dream/direct persistence hit.
Lifecycle-store internals may use the replacement storage name but source modules may only call
the admission contract.

## Source admission

Run the procedure package and source-adapter suites:

```bash
make test-memory
make test-automation
make test-workspace
make test-skills
```

Verify one fixture from each source class:

1. completed goal and completed workflow create candidates;
2. approved workspace run creates a candidate, unapproved run fails eligibility;
3. repeated action pattern creates evidence-backed candidate;
4. explicit user instruction retains prompt-supplied provenance;
5. reviewed dream/reflection artifact retains reviewer evidence;
6. imported skill creates a candidate without changing its execution access.

## Review, versioning, and feedback

1. Submit a complete evidence-backed candidate and approve it.
2. Retrieve procedures and confirm exactly one active admitted version appears.
3. Submit a material revision for the same identity; approve it and confirm v1 is superseded.
4. Record a failed use linked to an existing ActionRecord.
5. Roll back the active version; confirm a prior eligible version becomes active, or the
   identity is retired if none qualifies.
6. Confirm history retains both decisions, evidence/learning references, feedback, and lineage.

## Provisional resolution

Run goal executor tests for completion, abandonment, cancellation, and restart recovery. Every
provisional procedure must either become a candidate on completion or have a recorded discard
reason; none may remain in a process-local collection after terminal handling.

## Scope guard

Confirm no touched behavior expands imported-skill execution, `allowed-tools`, workspace
permissions, generic contribution arbitration, or generic ActionRecord production.
