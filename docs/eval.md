# Ze Eval — Using the Eval System

Ze's eval system lets any LLM-powered IDE (Claude Code, Cursor, Codex) interactively
send messages to Ze, inspect routing decisions, and evaluate whether Ze responded
correctly. The IDE's LLM is the judge — there is no fixed scoring function.

---

## Prerequisites

- Ze server running locally (`make dev` or `make dev-poll`)
- `ZE_API_KEY` from your `.env`

---

## Quick start (Claude Code)

1. **Set your API key** in `.claude/settings.local.json`:
   ```json
   "env": {
     "ZE_EVAL_URL": "http://localhost:8000",
     "ZE_API_KEY": "<your key from .env>"
   }
   ```

2. **Reload MCP servers** — in Claude Code: `/mcp` → restart, or restart the IDE.

3. **Use the tools.** Ask Claude Code anything like:

   > "Run the `companion_greeting` scenario against Ze and tell me if the response is in character."

   > "Run the full routing suite and identify which scenarios Ze gets wrong."

   > "Send Ze the message 'remind me to call mum tomorrow at 6pm' and evaluate whether it handles the reminders correctly."

---

## MCP Tools Reference

### `ze_chat`

Send a single message to Ze and get its response with routing metadata.

```
ze_chat(prompt="What time is it?", session_id="eval")
```

Returns:
- `response` — Ze's text response
- `agent_used` — which agent handled it (`companion`, `research`, `calendar`, etc.)
- `routing` — confidence, routing method, per-agent scores
- `pending_confirmation` — `true` if Ze paused to ask for user confirmation
- `error` — error message if the graph failed

Use the same `session_id` across calls to simulate a multi-turn conversation.
Use a fresh `session_id` for each independent test.

---

### `ze_list_scenarios`

List all available test scenarios.

```
ze_list_scenarios()                  # all scenarios
ze_list_scenarios(tag="routing")     # filtered by tag
```

Tags: `companion`, `routing`, `persona`, `research`, `calendar`, `email`,
`emotional`, `safety`, `compound`, `graceful_degradation`.

---

### `ze_run_scenario`

Run a named scenario and receive Ze's response alongside the scenario's
expected criteria. You (the evaluating LLM) read the criteria and judge whether
Ze's response passes.

```
ze_run_scenario(scenario_id="companion_greeting")
```

Returns the scenario definition, Ze's response, routing metadata, and a
`matches_expected_agent` boolean (if the scenario declares an `expected_agent`).

---

### `ze_run_suite`

Run all scenarios (or a filtered subset) in one call and get a summary.

```
ze_run_suite()               # all scenarios
ze_run_suite(tag="persona")  # persona scenarios only
```

Returns a summary with counts (`routing_correct`, `routing_wrong`, `errors`) and
per-scenario results for the evaluating LLM to review.

---

## The eval endpoint directly

If you prefer `curl` or want to integrate into your own script:

```bash
curl -X POST http://localhost:8000/eval/chat \
  -H "Content-Type: application/json" \
  -H "x-ze-api-key: <your-key>" \
  -d '{"prompt": "What is recursion?", "session_id": "test-1"}'
```

---

## Adding scenarios

Create or edit YAML files in `evals/scenarios/`. No code changes required.

```yaml
- id: my_new_scenario
  prompt: "The message Ze will receive"
  description: "What this is testing"
  expected_agent: companion          # optional — enables routing accuracy check
  tags: [companion, persona]
  criteria:                          # optional rubric hints for the evaluating LLM
    - Should respond warmly
    - Should not use corporate language
```

Run `ze_list_scenarios()` to confirm it appears.

---

## Notes

- Eval threads are namespaced as `eval-<session_id>` to avoid contaminating the
  user's real conversation history, but they share the same database. Ze may surface
  user memory in eval responses.
- If `pending_confirmation` is `true`, Ze would normally pause for user approval.
  The eval endpoint returns the draft response in `response` and does not auto-resume.
- Calendar and email scenarios require valid Google credentials in `.env`.
  Without them, Ze should return a graceful error — that is itself a valid eval outcome.
