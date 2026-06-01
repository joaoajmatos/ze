# <Module Name> — Spec

> **Package:** `ze_core` | `ze_personal` | `ze` | `ze_browser`
> **Phase:** N
> **Status:** Done | In Progress | Pending | Deprecated

---

## Implementation Status

<!-- Fill in once implementation starts. Remove this section for pure design specs. -->

| Feature | Status |
|---------|--------|
| Core types | 🔲 Pending |
| Storage layer | 🔲 Pending |
| Tests | 🔲 Pending |

---

## Purpose

<!-- One paragraph: what problem does this module solve? Why does it exist? -->

---

## Responsibilities

<!-- Bulleted list: what this module owns and enforces. -->

- ...

---

## Out of Scope

<!-- Bulleted list: what explicitly does NOT belong here. Prevents scope creep. -->

- ...

---

## Module Location

```
packages/<package>/
  <module>/
    __init__.py
    types.py
    store.py
    ...
```

---

## Interface Contract

<!-- Public API: function signatures, class constructors, return types. -->

### Input

```python
...
```

### Output

```python
...
```

### Errors / Edge Cases

| Condition | Behaviour |
|-----------|-----------|
| ... | ... |

---

## Data Structures

<!-- Key dataclasses. Use ze convention: dataclasses in types.py, no Pydantic in domain. -->

```python
# packages/<package>/<module>/types.py

@dataclass
class Foo:
    id: str
    ...
```

---

## Database Schema

<!-- Alembic raw SQL. Include table name, columns, indexes, FKs. Omit if no DB interaction. -->

```sql
CREATE TABLE foo (
    id          TEXT PRIMARY KEY,
    ...
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## Configuration

<!-- Config keys from config.yaml, .env vars, or class attributes. -->

```yaml
# config/config.yaml
foo:
  setting: value
```

---

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `ze_core.errors` | Typed error hierarchy |
| ... | ... |

---

## Implementation Notes

<!-- Non-obvious decisions, invariants, or workarounds that would surprise a future reader. -->

---

## Open Questions

<!-- Track unresolved questions. Mark resolved with [x] and the decision taken. -->

- [ ] ...
