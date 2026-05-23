# Ze — Configuration Reference

Ze has two layers of configuration:

- **`.env`** — secrets and deployment-specific values. Never committed.
- **`config/config.yaml`** — all structural and behavioural settings. Committed.

---

## `.env`

Copy `.env.example` to `.env` and fill in every value before starting the server.

### API keys

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key — all LLM calls go through this |
| `TAVILY_API_KEY` | Yes | Tavily API key — used by the research agent |
| `ZE_API_KEY` | Yes | Static bearer token for REST endpoints (`Authorization: Bearer <token>`) |

### Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://ze:ze@localhost:5432/ze` | asyncpg connection URL (runtime) |
| `DATABASE_URL_SYNC` | `postgresql+psycopg2://ze:ze@localhost:5432/ze` | psycopg2 URL for Alembic CLI |

### Telegram

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | Token from @BotFather |
| `TELEGRAM_WEBHOOK_SECRET` | Prod only | Arbitrary secret used to verify Telegram POSTs via `X-Telegram-Bot-Api-Secret-Token` |
| `TELEGRAM_ALLOWED_CHAT_ID` | Yes | Your personal Telegram chat ID (integer). All other chat IDs are silently ignored. |
| `PUBLIC_URL` | Prod only | HTTPS base URL (e.g. `https://ze.fly.dev`). Omit or leave empty in local dev — polling mode needs no URL. |

### Google (Calendar + Gmail)

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_CLIENT_ID` | If using calendar/email | OAuth2 client ID from Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | If using calendar/email | OAuth2 client secret |
| `GOOGLE_REFRESH_TOKEN` | If using calendar/email | Long-lived refresh token. Obtained by running `scripts/google_auth.py` once locally; stored as a Fly secret in production. |
| `TIMEZONE` | No | IANA timezone string (default: `UTC`). Used for calendar reminders and morning briefing scheduling. |

### Runtime behaviour

| Variable | Default | Description |
|---|---|---|
| `CONFIRM_TIMEOUT_SECONDS` | `900` | How long (seconds) a `confirm`-mode graph pause waits before expiring |
| `LOG_LEVEL` | `INFO` | Structlog level: `DEBUG` / `INFO` / `WARNING` |

---

## `config/config.yaml`

This file controls routing, model assignments, persona, memory, proactive behaviour,
and per-agent settings. It is read at startup; some sections hot-reload on `SIGHUP`.

### `routing:`

Controls how the embedding router classifies incoming messages.

```yaml
routing:
  threshold: 0.55         # Minimum cosine similarity to route directly to an agent
  gap_threshold: 0.10     # Minimum gap between top two scores; below this → compound task
  embedding_model: all-MiniLM-L6-v2   # Local sentence-transformer model name
  fallback_model: anthropic/claude-haiku-4-5  # LLM used when embedding routing is ambiguous
```

- Raise `threshold` to make direct routing more conservative (more Haiku fallbacks).
- Raise `gap_threshold` to decompose more messages as compound tasks.

### `models:`

System-level model assignments for internal flows. These are not agent models.

```yaml
models:
  router:         anthropic/claude-haiku-4-5   # Haiku fallback + fact dedup merge decisions
  synthesis:      anthropic/claude-haiku-4-5   # Multi-agent response synthesis + episode summaries
  profile:        anthropic/claude-haiku-4-5   # User profile synthesis
  reminders:      anthropic/claude-haiku-4-5   # Calendar reminder interval assessment
  insights:       anthropic/claude-haiku-4-5   # Weekly insight generation
  whisper:        openai/whisper-1             # Voice note transcription
  vision_caption: google/gemini-flash-1.5      # Cheap routing caption for photos (no text)
```

`whisper` is used by `TranscriptionClient` to convert OGG voice notes to text before
the graph runs. `vision_caption` is called at `embed_route` when a photo arrives
without a text caption, so the embedding router has text to score against agent
embeddings. Both models are invoked via OpenRouter.

### `persona:`

Controls Ze's tone across all agent responses via named profiles and continuous dials.

```yaml
persona:
  profile: default   # Active profile name. Overridden at runtime via /persona command.
  locale: en         # BCP 47 locale for progress message translations (en | pt)

  profiles:
    default:
      traits: [direct, warm, concise]
      verbosity: concise        # concise | balanced | detailed
      custom_instructions: ""   # Free-form text appended after traits, before memory context
      dials:
        humor:       0.3        # 0 = none → 1 = freely witty
        directness:  0.9        # 0 = Socratic → 1 = blunt conclusions-first
        formality:   0.2        # 0 = casual → 1 = formal
        depth:       0.5        # 0 = surface → 1 = full elaboration

    stoic:
      traits: [precise, measured]
      verbosity: concise
      custom_instructions: ""
      dials:
        humor: 0.05
        directness: 1.0
        formality: 0.7
        depth: 0.4

    playful:
      traits: [warm, curious, witty]
      verbosity: balanced
      custom_instructions: ""
      dials:
        humor: 0.85
        directness: 0.4
        formality: 0.1
        depth: 0.6
```

**Profiles** are named personality presets. Add as many as you like under `profiles:`.
The `profile:` key sets the YAML default; the active profile is overridden at runtime
by the DB value set via `/persona` commands and survives process restarts.

**Dials** are continuous `[0.0, 1.0]` values. Each dial maps to a prose clause injected
into the identity block only at the extremes (below `0.2` or above `0.8`). The neutral
band `[0.2, 0.8)` is intentionally silent — no instruction is added, keeping the system
prompt compact for untuned dials.

| Dial | Low (< 0.2) effect | High (≥ 0.8) effect |
|---|---|---|
| `humor` | No humor | Openly funny |
| `directness` | Socratic / exploratory | Conclusions first, no preamble |
| `formality` | Casual, first names | Formal and precise |
| `depth` | Surface level | Full elaboration with examples |

**`custom_instructions`** is free-form text appended to every system prompt for that
profile — useful for "Always respond in European Portuguese" or "Use my name João."

**Runtime switching** via Telegram:

```
/persona                    # show current profile + dial values
/persona stoic              # switch to named profile (resets dial overrides)
/persona humor 0.8          # override one dial on the active profile
/persona reset              # restore all dials to profile YAML defaults
```

Profile switches and dial overrides are persisted in the `persona_state` DB table and
survive restarts. The inline keyboard attached to `/persona` allows one-tap profile switching.

### `memory:`

```yaml
memory:
  contradiction_threshold: 0.85   # Cosine similarity above which two facts are candidates for dedup

  consolidation:
    merge_silent_threshold: 0.95  # Above this → merge without LLM confirmation
    merge_llm_threshold: 0.85     # Above this (below silent) → LLM decides whether to merge
    contradicted_ttl_days: 30     # Hard-delete contradicted facts after N days
    unreviewed_ttl_days: 90       # Soft-expire unreviewed facts after N days
    expiry_grace_days: 7          # Days between soft-expire and hard-delete
    episode_recency_days: 14      # Never archive episodes newer than N days
    episode_archive_batch: 20     # Episodes per archive run
    episode_min_archive_batch: 10 # Min unarchived episodes required to trigger a run
    nightly_cron: "0 2 * * *"     # When consolidation runs (2 AM UTC default)

  profile:
    min_facts: 3       # Skip profile synthesis below this many reviewed facts
    episode_limit: 50  # Max episodes fed into the synthesis prompt

  insights:
    lookback_days: 7   # Evidence window for insight generation
    min_evidence: 3    # Min combined facts + episodes required to produce insights
    max_per_run: 3     # Max insights pushed per weekly run
```

### `proactive:`

Controls the three proactive push behaviours.

```yaml
proactive:
  briefing:
    enabled: true
    cron: "0 8 * * *"               # When to send the morning briefing (cron, UTC)
    unreviewed_nudge_threshold: 5   # Include a review nudge if unreviewed facts >= this

  alerts:
    workflow_failure_enabled: true
    workflow_failure_cooldown_hours: 1  # Min hours between repeated alerts for the same workflow

  calendar:
    sync_enabled: true
    sync_cron: "45 7 * * *"   # When to sync Google Calendar for reminders (before briefing)
    sync_days_ahead: 7        # How many days ahead to pull events

  insights:
    enabled: true
    cron: "0 7 * * 0"           # When to run insight generation (Sunday 7 AM UTC)
    category_cooldown_days: 7   # Suppress same insight category within this window
```

Disable any proactive feature by setting `enabled: false` or toggling the relevant flag.

### `agents:`

Per-agent configuration. Each agent block controls:

```yaml
agents:
  <name>:
    enabled: true | false           # false → agent is excluded from routing
    description: |                  # Embedded for cosine-similarity routing
      One or more sentences describing what this agent handles.
    model: anthropic/...            # Primary model for this agent
    model_simple: anthropic/...     # Optional cheaper model for simple requests (cost-aware routing)
    vision_capable: true | false    # If true, agent receives ChatContentImage for photo inputs
    tools:
      - tool_name                   # Tools available to this agent
    timeout_seconds: 30             # asyncio.wait_for timeout for agent.run()
    intent_map:
      intent_key: "description"     # Maps intent names to tool descriptions
    capabilities:
      intent_key: autonomous | confirm | draft_only | disabled
```

**`vision_capable`** — when `true`, the `execute_tool` node passes raw image bytes to
the agent as a `ChatContentImage` content block alongside the text prompt. When `false`
(or omitted), the agent receives only the routing caption generated at `embed_route`.
All current agents have `vision_capable: true`.

**Capability modes:**

| Mode | Behaviour |
|---|---|
| `autonomous` | Execute immediately, no user prompt |
| `confirm` | Pause graph, send inline keyboard (Yes / No / Edit). Timeout: `CONFIRM_TIMEOUT_SECONDS`. |
| `draft_only` | Generate and show the proposed action, never execute |
| `disabled` | Block entirely, return an error message |

**Cost-aware routing:** if `model_simple` is set, the in-process complexity classifier
may select it for short/simple requests. Agents that already use Haiku (e.g. `calendar`,
`email`) should omit `model_simple` — there is no cheaper tier to fall back to.

#### Default agent capabilities

| Agent | Intent | Default mode |
|---|---|---|
| `research` | `read` | `autonomous` |
| `research` | `execute` | `confirm` |
| `companion` | `reason` | `autonomous` |
| `calendar` | `read` | `autonomous` |
| `calendar` | `create` / `update` / `delete` | `confirm` |
| `email` | `read` | `autonomous` |
| `email` | `create` / `update` | `draft_only` |
| `email` | `delete` | `confirm` |
| `workflow` | `read` | `autonomous` |
| `workflow` | `manage` | `confirm` |

---

## Enabling calendar and email

Both agents default to `enabled: false` because they require Google OAuth2 credentials.

1. Create a Google Cloud project, enable Calendar and Gmail APIs.
2. Create an OAuth2 client ID (Desktop application type).
3. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`.
4. Run the one-time auth script locally:
   ```bash
   python scripts/google_auth.py
   ```
   This opens a browser, completes the OAuth flow, and prints the refresh token.
5. Set `GOOGLE_REFRESH_TOKEN` in `.env` (locally) or as a Fly secret (production).
6. Set `calendar.enabled: true` and/or `email.enabled: true` in `config/config.yaml`.

---

## Hot-reloading

Send `SIGHUP` to the running process to reload capability modes and persona settings
without restarting:

```bash
kill -HUP <pid>
# or on Fly.io:
fly ssh console -C "kill -HUP 1"
```

Agent `enabled` flags and model assignments require a full restart.
