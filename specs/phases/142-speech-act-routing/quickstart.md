# Quickstart: Speech-Act Routing (Phase 142)

## Prerequisites

Phase 140 implemented (`remember_fact` / `forget_fact` + admission gate).

## Validate

```bash
make test-memory
make test-personal
make lint
```

## Table tests (minimum)

| Utterance | Expect |
|---|---|
| Prefer aisle seats / remember that | fact tool; no reminder |
| Forget aisle seats | forget_fact |
| Remind me Tuesday 15:00 dentist | reminder handoff; 0 facts |
| Remember to call Mom Tuesday 15:00 | reminder; 0 facts |
| I’ll call Mom Tuesday | reminder or loop; 0 facts |
| Figure out job switch | loop; 0 facts |
| Ship thesis by June | goal handoff; 0 facts |
| Never email after 22:00 | constraint fact; mail tools still listed |
| Weather / filler | drop |
