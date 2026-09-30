# Contract: OpenRouter System One HTTP

**Feature**: `162-system-one-client`  
**Verbatim**: `typesafe/jev-1.13`, `OPENROUTER_API_KEY`, Principle VII

Upstream: [Submit a System One request](https://openrouter.ai/docs/api/api-reference/systemone/submit-a-system-one-request). TypeSafe-compatible body.

## Endpoint

`POST {openrouter_base_url}/systemone`

Default `openrouter_base_url` is already `https://openrouter.ai/api/v1`, so the path is `https://openrouter.ai/api/v1/systemone`.

## Auth and headers

| Header | Value |
|---|---|
| `Authorization` | `Bearer {OPENROUTER_API_KEY}` |
| `Content-Type` | `application/json` |
| `HTTP-Referer` | same as `OpenRouterClient` |
| `X-OpenRouter-Title` | same as `OpenRouterClient` |

No `TYPESAFE_API_KEY`. Empty key → skip `missing_key` (no POST).

## Request body

```json
{
  "model": "typesafe/jev-1.13",
  "state": { "ticket": "…" },
  "questions": {
    "is_bug": {
      "type": "noul",
      "instructions": "Is the customer reporting a software defect?",
      "criteria": { "true": "…", "false": "…" }
    },
    "team": {
      "type": "choice",
      "instructions": "Which team should own this ticket?",
      "criteria": { "account": "…", "payments": "…" }
    },
    "urgency": {
      "type": "score",
      "instructions": "How urgent is this ticket?",
      "criteria": ["Can wait", "This week", "Blocking"]
    }
  }
}
```

`state` MAY be a string. `model` comes from YAML `system_one.model` (pin `typesafe/jev-1.13`, not `jev-latest`).

Do **not** send this body to `/chat/completions`. Do **not** use `POST /api/alpha/decisions` in 162.

## Success response (shape)

```json
{
  "id": "gen-dec-…",
  "model": "typesafe/jev-1.13-20260917",
  "provider": "TypeSafe",
  "answers": {
    "is_bug": { "type": "noul", "noul": 0.96 },
    "team": {
      "type": "choice",
      "choice": "payments",
      "confidence": 0.75,
      "probabilities": { "account": 0, "frontend": 0.16, "payments": 0.84 }
    },
    "urgency": {
      "type": "score",
      "score": 1.99,
      "confidence": 0.99,
      "probabilities": { "0": 0, "1": 0.01, "2": 0.99 }
    }
  },
  "usage": { "input_tokens": 275, "output_tokens": 20, "cost": 0.00003 }
}
```

Map into `SystemOneResult`. Persist the **reported** `model` on the trace, not only the request alias.

## Fail-open HTTP mapping

| Condition | `skip_reason` |
|---|---|
| `enabled: false` | `disabled` |
| Missing/blank API key | `missing_key` |
| Timeout (`timeout_ms`) | `timeout` |
| HTTP 429 or 529 | `overload` |
| HTTP 5xx after retries (same 429/5xx retry budget as chat: 1s/2s/4s, then skip) | `overload` or `error` |
| HTTP 4xx other than 429, or malformed JSON | `error` (log; do not raise) |

Retries MUST NOT turn a skip into a graph exception.

## Tests

Mock `httpx` (or the SDK method). Default tests MUST NOT perform a live POST. Live calls, if ever added, are `@pytest.mark.slow` and opt-in.
