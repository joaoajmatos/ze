# Ze Eval — Spec

## Implementation Status

| Feature | Status |
|---------|--------|
| `POST /eval/chat` endpoint | ✅ Done |
| `ZeBot.invoke()` — graph invocation without Telegram | ✅ Done |
| `EvalChatRequest` / `EvalChatResponse` schemas | ✅ Done |
| MCP server (`evals/mcp_server.py`) | ✅ Done |
| HTTP client (`evals/client.py`) | ✅ Done |
| Scenario library (`evals/scenarios/`) | ✅ Done |
| Claude Code MCP configuration (`.claude/settings.local.json`) | ✅ Done |
| `make eval-server` Makefile target | ✅ Done |
| This spec + `docs/eval.md` | ✅ Done |

---

## Purpose

Ze has unit tests for individual modules, but no end-to-end signal for whether Ze
actually behaves well as a whole. The eval system provides that signal by letting
any LLM-powered IDE (Claude Code, Cursor, Codex) interactively send messages to Ze,
inspect how it routed and responded, and use its own judgement to evaluate quality.

The key design choice: **the calling LLM is the judge**. There is no baked-in
scoring function. The eval system exposes Ze's behaviour as MCP tools; the IDE's
LLM reads the output and reasons about whether it is correct. This is more flexible
than a fixed rubric and naturally improves as the judge model improves.

---

## Out of Scope

- Voice and image eval (text-only via `POST /eval/chat`).
- Confirmation flow simulation — if Ze pauses for confirmation, `pending_confirmation`
  is returned in the response but no auto-resume is performed.
- Persistent result storage — results are returned in-process; callers decide whether
  to store them (e.g. by pasting into a document or writing to a file).
- CI gating — the eval is a developer tool, not a CI check. It requires a running
  Ze server with a real database and OpenRouter access.
- Multi-user eval or isolated eval environments — Ze's database state (memory, routing
  log) is shared with the real user session. Eval threads are namespaced with
  `eval-<session_id>` thread IDs to limit contamination, but not fully isolated.

---

## Repository Layout

```
ze/
├── api/
│   └── routes/
│       └── eval.py              # POST /eval/chat
├── api/
│   └── schemas.py               # EvalChatRequest, EvalChatResponse, EvalRoutingInfo
└── telegram/
    └── bot.py                   # ZeBot.invoke() — core graph invocation
evals/
├── __init__.py
├── client.py                    # ZeEvalClient (async httpx wrapper)
├── mcp_server.py                # FastMCP stdio server
└── scenarios/
    ├── companion.yaml
    ├── routing.yaml
    └── persona.yaml
.claude/
└── settings.local.json          # MCP server wiring for Claude Code
```

---

## Data Flow

```
IDE LLM (Claude Code / Cursor / Codex)
        │
        │  MCP tool call (ze_chat / ze_run_scenario / ze_run_suite)
        ▼
evals/mcp_server.py  ──── HTTP POST /eval/chat ────► ze/api/routes/eval.py
                                                              │
                                                     ZeBot.invoke(prompt, session_id)
                                                              │
                                                     graph.ainvoke(state, config)
                                                              │
                                                      ┌───────────────┐
                                                      │  LangGraph    │
                                                      │  embed_route  │
                                                      │  fetch_context│
                                                      │  execute_tool │
                                                      │  write_memory │
                                                      └───────────────┘
                                                              │
                                              EvalChatResponse (JSON)
                                                  response, agent_used,
                                                  routing, confidence,
                                                  raw_scores, error
                                                              │
        ◄─────────────────────────────────────────────────────┘
        │
   IDE LLM evaluates response against scenario criteria using its own reasoning
```

---

## API

### `POST /eval/chat`

**Auth:** `x-ze-api-key` header (same as the rest of the API).

**Request:**
```json
{
  "prompt": "What time is it?",
  "session_id": "eval"
}
```

`session_id` controls the LangGraph `thread_id` (namespaced as `eval-<session_id>`).
The same `session_id` across requests maintains conversation history. Use a fresh
`session_id` for each independent test.

**Response:**
```json
{
  "session_id": "eval",
  "response": "I don't have access to a real-time clock...",
  "agent_used": "companion",
  "routing": {
    "primary_agent": "companion",
    "confidence": 0.87,
    "routing_method": "embedding",
    "is_compound": false,
    "score_gap": 0.23,
    "raw_scores": { "companion": 0.87, "research": 0.64, "calendar": 0.41 }
  },
  "pending_confirmation": false,
  "error": null
}
```

---

## MCP Tools

Exposed by `evals/mcp_server.py` via the stdio MCP protocol.

| Tool | Description |
|------|-------------|
| `ze_chat(prompt, session_id?)` | Send one message to Ze, return structured JSON response |
| `ze_list_scenarios(tag?)` | List scenario definitions from `evals/scenarios/` |
| `ze_run_scenario(scenario_id)` | Run a named scenario, return response alongside criteria |
| `ze_run_suite(tag?)` | Run all scenarios, return per-scenario results + summary counts |

---

## Scenario Format

Each file in `evals/scenarios/` is a YAML list of scenario objects:

```yaml
- id: routing_research_factual         # unique identifier
  prompt: "What are the differences between PostgreSQL and MySQL?"
  description: "Clear factual research query — should route to research agent"
  expected_agent: research             # optional — enables routing accuracy check
  tags: [routing, research]            # for filtering via ze_list_scenarios / ze_run_suite
  criteria:                            # optional rubric hints for the evaluating LLM
    - Should be handled by the research agent
    - Should provide a substantive, accurate comparison
```

Add new scenarios by creating or editing YAML files. No code changes required.

---

## Resolved Decisions

**Why not a fixed LLM judge?**
A fixed rubric requires knowing in advance what "correct" looks like. The eval
library doesn't know Ze's persona, current memory state, or instruction changes.
Delegating judgement to the calling LLM means evaluation improves automatically
as Ze's instructions change, and the evaluator can reason about context.

**Why MCP rather than a CLI?**
An MCP server integrates directly into the IDE conversation. The evaluating LLM
can interleave tool calls (run a scenario, read the output, form a hypothesis,
run another scenario to test it) in the same context window where it is also
reading Ze's source code. This makes eval-then-fix loops possible in one session.

**Why not Telegram simulation?**
Constructing aiogram `Update` objects is brittle and tightly coupled to aiogram
internals. Invoking the LangGraph directly via `ZeBot.invoke()` tests everything
except the Telegram message parsing layer, which has no logic worth testing.

**Why namespace eval thread IDs?**
Eval runs share Ze's real database (memory, routing log). Prefixing thread IDs
with `eval-` ensures eval conversation history doesn't bleed into the user's
real conversation, and makes it easy to identify eval-originated entries in the
routing log.
