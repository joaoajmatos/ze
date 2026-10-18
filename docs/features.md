# Ze — Feature inventory

This page lists what Ze does today, one area at a time. For the short version, read the [README](../README.md). For the design behind it, read the [doctrine](../specs/arch/ze-doctrine.md) and [cognitive architecture](cognitive-architecture.md).

Ze is a Python/FastAPI backend with LangGraph orchestration, a React web client, and one plugin per domain. By default, routing uses local embeddings (`intfloat/multilingual-e5-base`), so no LLM call happens until an agent needs to act. All LLM traffic goes through OpenRouter. Postgres checkpoints graph state, so it survives restarts.

- **ze-web** — React SPA (Feature-Sliced Design). `@myguyze/ze-client` is generated from the OpenAPI spec. `@myguyze/ze-ui` renders server-driven components, including charts.

## One voice, many specialists

Companion is the only agent that speaks to you. It acts as the conductor: when a request needs several specialists in sequence, the router sends it to companion, and companion calls them through one `delegate_to_agent` tool. Each call carries a full brief, runs in an isolated worker, and passes its own write confirmation check. Independent requests (for example, "check my calendar and summarize the news") still fan out in parallel in the graph and merge in a `synthesize` step. Work that must outlive the turn becomes a goal or a workflow; companion can promote a conductor run into either one.

## Ask

Ask answers with an assembled canvas, not a chat bubble. The reply is a sentence plus one module per part of the answer: a headline, claim cards, a timeline, a chart or a table. Each module can be pinned, dismissed or asked about. Preset questions ("What's slipping?") come from stored records, not from a model. Every reply has a trace, drawn as a rail of instruments: the path of the turn, how the specialist was chosen, what Ze remembered, which tools ran, what System One was asked, and what a retry undid. A write that needs your OK asks in place, in the canvas or in the overlay. If another window holds the connection, every place says so and offers Use here.

## System One

System One is a small model that returns typed judgments (a choice among labels, a yes/no probability, a score), never free text. Ze treats it as a fast gate, with code making the final decision. Five surfaces use it:

- **Commitment intake** decides what a finished conversation turn committed the user to: a durable fact worth keeping, a loop to open or close, or a link to a reminder or goal the turn already created.
- **Routing choice** picks among the agents E5 shortlisted, decides whether the request needs more than one specialist, and grades how complex it is.
- **Skill gating** picks at most one automatic skill from the skills E5 shortlisted.
- **Loop gate** decides whether email, calendar, or ingested text opens or resolves an open loop.
- **Corroboration** decides whether an independent source is about the same open matter as a suspected loop, and can promote it.

Five of the six surfaces are on in the shipped config, each with bars measured on a labeled set (`make calibrate-commitment-intake`, `make calibrate-routing`, `make calibrate-skills`, `make calibrate-loop-gate`, `make calibrate-complexity`); the corroboration surface ships off until `make calibrate-corroboration` gives a held-out `ENABLE`. The code defaults are off. When a surface is off, uncalibrated, or skips, Ze falls back to the older path: the E5 thresholds and the Haiku judge for routing and skills, the Haiku fact extractor and loop gate for the commitment intake, the Haiku judge for the loop gate, the plain evidence link for corroboration, and the agent's full model for complexity. See [configuration.md](configuration.md#system_one).

## Goal engine

Hand Ze an objective and it decomposes into milestones, dispatches them to specialist agents on a schedule, pauses at verification gates with a progress narrative, replans on failure, and writes a retrospective when it finishes. Steer mid-flight by talking — no slash commands. Background sweep runs every 15 minutes regardless of whether you're online.

Goals are the heavyweight, declared end of Ze's executive function. Most real commitments never get declared as a goal.

Doing shows what runs without you. It lists goals, workflows, workspace runs and skill reviews on one page. There you start a planned goal, answer its gates, and redirect, pause or abandon a stuck one. You can also review held writes and cancel a run.

World, the home screen, ranks drifting loops, stuck goals, and correlation hypotheses on one scale, and plots them by time left and how sure Ze is. You can reorder items by dragging them (or with the keyboard) or by telling Ze ("that can wait"). You can also approve held writes, answer goal checkpoints and confirm suspected loops without leaving it. Your overrides decay or stay pinned, and they feed the same ranking that decides what Ze mentions in conversation and what it pushes. When Ze cannot read a source, the page names it.

## Open loops

Most of what someone means to follow up on is smaller than a goal: a promise made in an email thread, a decision left pending, a project quietly stalling because a dependency didn't land. `ze-worldstate` tracks these as open loops, extracted from conversation, email, calendar, and ingestion. Extraction is gated: three System One yes/no questions decide whether text opens, declares, or resolves a loop, and Haiku writes only the title. If System One skips, the older Haiku judge runs as the fallback. Confidence decays on its own; a contradiction or a missed deadline moves a loop to `drifting`. You can also ask Ze to keep something on the radar ("keep the Porto move on my radar"). The `loops` agent creates that loop in the same turn with the `track_loop` tool, and the post-turn gate skips that turn. When a later independent source matches a suspected loop, Ze asks one System One same-concern question, raises the loop's confidence, and can promote it to `active`; the loop records each source, and the Open loops page labels it "Promoted · seen in: chat, email". At the start of a new session, Ze asks whether to keep track of up to three loops it noticed. If the reply skips the question, Ze adds a short one in your language (English or Portuguese). Ask "what's still on my plate?" and the answer comes from the merged priority ranking, not from one agent's own list. The Open loops page (Automation) lists them for review. Drifting loops surface inline in the next relevant conversation, or push through ntfy once they clear the salience bar. Loop pushes are discretionary, so they share one daily budget with every other unprompted nudge, and quiet hours hold them like the rest.

![State machine showing an open loop moving from suspected to active, by an independent corroboration or a confirmation, then to drifting, where a contradiction or a missed deadline is the guard that triggers drift, and drifting loops finally resolving to closed or dropped](diagrams/root/open-loops.svg)

<sub>[Interactive version](diagrams/root/open-loops.html)</sub>

Goals and open loops are Ze's two hands of executive function: one heavyweight and declared, one lightweight and ambient. Together they're the shipped first slice of what the doctrine calls **active concerns** — the fourth face of Ze's world-state, the model of you the rest of the system attaches to. See [the doctrine](../specs/arch/ze-doctrine.md) and [cognitive architecture](cognitive-architecture.md).

Hypotheses Ze forms from cross-domain evidence are listed over REST, and you can dismiss one (not relevant, or muted). A dismissed hypothesis is no longer pushed, ranked or offered in conversation, and clearing the dismissal brings it back. Dismissal applies to that one hypothesis: if Ze later forms the same connection again, it is a new hypothesis. A confirmed hypothesis stays listed as confirmed whatever its feedback. Reminders are listed over REST as upcoming, overdue or fired. Confidence values are stored in single precision and only the last change is kept, so clients should round and compare with a tolerance.

## Memory

Ze extracts facts and episodes after each turn, consolidates them nightly, and synthesizes a profile weekly. `pgvector` handles retrieval. Several rules keep the store honest:

- **Admission.** A keep/drop extractor decides what becomes a fact. Facts enter through typed contributions with provenance and confidence, and a constraint check can veto a write.
- **Say it, and Ze remembers it.** You can tell companion to remember or forget something. Ze says it remembered or forgot something only after the write succeeds.
- **Read contract.** Facts you reviewed are always in context. Ze shows the origin, confidence, and age of each fact to the model, and it uses facts silently instead of reciting them.
- **Evidence-backed learning.** Ze logs what its agents did in an append-only action ledger. Goal learnings cite that evidence, and Ze promotes them to long-term memory on completion.
- **Mind.** The Mind place shows what Ze believes, with each belief's kind, confidence, source and age, and lets you keep, edit or drop it. You can search any person, place or project and see what Ze knows around it, review the procedures Ze proposes, and see the people Ze knows.
- **Procedures.** Ze proposes a procedure when it detects a reusable multi-step pattern. The proposal goes through admission and validation before it becomes available. Companion can then invoke it as advisory guidance. A procedure never grants new tool access.

## Dreaming

Every night Ze runs an offline memory improvement loop — sleep pass then dream pass. The sleep pass replays high-priority episodes, compresses old sessions, deduplicates facts, and identifies schema and policy clusters using only structural analysis (no LLM calls). The dream pass then synthesizes those clusters into insights, procedures, and plan stress-tests using a haiku-class generator.

Nothing synthetic goes straight to memory. Every artifact passes three cheap pre-gates (NLI groundedness, embedding novelty, retrievability) and two adversarial LLM critic calls at sonnet-class before reaching a morning integration step that enforces session-diversity and temporal-spread requirements. Promoted facts carry full lineage for per-run rollback. Borderline cases surface in the morning briefing for review. Synthetic facts that go uncorroborated for 90 days are automatically expired.

The design is drawn from neuroscience (NREM/REM ordering, targeted memory reactivation) and ML (PER, Constitutional AI-style critic filtering, generative replay safety). It's the first layer of Ze becoming genuinely self-improving rather than just accumulating facts.

## How Ze gets sharper

Memory isn't a single inflow. Everything feeds the same substrate:

![Architecture diagram showing conversation, ingestion, and domain-event inflows feeding extraction, an admission gate for signals, and a central memory graph that feeds retrieval and a correlation engine](diagrams/root/memory-inflow.svg)

<sub>[Interactive version](diagrams/root/memory-inflow.html)</sub>

Conversations write what Ze learns from talking. Ingestion (`ze-ingestion`) feeds knowledge from any URL, PDF, YouTube video, or file — extracted facts land in the same store. Domain plugins emit `SignalSource` events; Ze scores them for relevance, writes them to the memory graph, and feeds them into the correlation engine. Goals promote learnings on completion. Every inflow compounds.

The design intent is that Ze gets sharper without being explicitly fed. Drop a PDF in. Share a video. The facts join everything else Ze already knows.

Every domain plugin also declares a `DataDomain` — an export, import, and delete contract. The portability service honours it. You own the data at every layer.

## Proactive surface

Ze doesn't wait to be asked. Morning briefings, calendar reminders, weekly insights, goal suggestions, stuck-goal alerts, news fetch — all background jobs, configurable in `config.yaml`. Every push declares a class: reminders you set always fire, reports you switched on are never budgeted, and only discretionary nudges claim one shared budget, counted over a rolling 24 hours. The budget, the next free slot and what each job last ran are visible over REST. Quiet hours hold everything but reminders, then release it as a batch. After downtime, a job that missed its time runs once. Offline push goes through ntfy; the in-app notification center (REST + WebSocket) surfaces the same events while you're in ze-web.

## Agents

Thirteen agents: research, companion, calendar, messenger, reminders, workflow, goals, loops, priority, prospecting, news, ingestion, finance. Each runs in a ReAct loop via `BaseAgent`. Agents can also use imported Agent Skills (`SKILL.md`), which you review before they take effect, and a chat-first workspace: an isolated computer with files and a shell, reached through chat.

Ze asks before it does anything it cannot undo. An irreversible write waits until you approve that exact action. Reads and reversible writes run without asking. A turn shows one confirmation card for all the writes it parked, and a denied write is reported as not done.

<details>
<summary>Agent reference</summary>

| Agent | Domain | Default posture |
|---|---|---|
| `research` | Web search + synthesis, delegation | Autonomous |
| `companion` | Reasoning, writing, conversation | Autonomous |
| `calendar` | Google Calendar CRUD + availability | Read auto · irreversible writes ask first |
| `messenger` | Cross-channel messaging (Gmail) | Read auto · sends ask first |
| `reminders` | NL reminders + proactive push | Autonomous |
| `workflow` | Recurring multi-step tasks | Read auto · irreversible changes ask first |
| `goals` | Multi-week autonomous objectives | Read auto · irreversible writes ask first |
| `loops` | List, track, confirm, close, or drop open loops | Autonomous |
| `priority` | Reorder what Ze treats as most important | Irreversible writes ask first |
| `prospecting` | Browser-sidecar research + outreach | Autonomous |
| `news` | Personalized RSS headlines + search | Autonomous |
| `ingestion` | URL / PDF / video / audio / text → memory | Autonomous |
| `finance` | Portfolio, spending, recurring expenses (Trading212 + CSV) | Read auto · irreversible writes ask first |

</details>

## Plugin extension surface

`ZePlugin` is the seam. A domain package hooks in by declaring what it contributes:

| Hook | What it provides |
|---|---|
| `agents()` | Agents registered into the routing graph |
| `ingestion_extractors()` | Domain-specific extractors (e.g. `TransactionExtractor` for PDFs) |
| `ingestion_fetchers()` | Custom content fetchers (e.g. Notion, proprietary APIs) |
| `signal_sources()` | Domain events fed into the correlation pipeline |
| `data_domains()` | Export / import / delete contract for every table the plugin owns |
| `memory_policies()` | Per-agent retrieval strategy from the memory graph |
| `channels()` | Communication channels (email, etc.) |
| `jobs()` | Proactive background jobs |
| `bundled_skill_paths()` | Agent Skills that ship with the plugin |
| `ui_contributions()` | Nav items, settings sections, plugin pages in ze-web |
| `rest_routes()` | Plugin-owned REST routers under `/api/v0/` |

The hooks compose. The finance plugin registers a `TransactionExtractor` so that ingesting a bank statement produces structured transaction facts — which land in memory, which surface in retrieval, which the correlation engine can cross with calendar and news. That chain is the whole point.

## Monorepo

```
apps/           ze-api · ze-web
plugins/        personal · messenger · calendar · news · prospecting · finance
core/           kernel/       ze-logging · ze-data · ze-components
                contracts/    ze-agents · ze-communication · ze-plugin · ze-proactive
                engine/       ze-core
                seam/         ze-collision
                cognition/    ze-memory · ze-correlation · ze-worldstate
                automation/   ze-automation · ze-skills
                arbitration/  ze-priority
                ops/          ze-workspace · ze-onboarding · ze-ingestion · ze-seed · ze-eval
packages/       ze-sdk · ze-client · ze-ui
integrations/   ze-google · ze-browser · ze-notifications · ze-trading212 · ze-yt
sidecar/        browser (Playwright) · workspace (isolated computer)
specs/          one spec per phase, written before the code
```

| Layer | Tech |
|---|---|
| Runtime | Python 3.12 · FastAPI · LangGraph · AsyncPostgresSaver |
| Client | React · Vite · TypeScript · Tailwind · shadcn/ui |
| LLM | OpenRouter · local embeddings (`intfloat/multilingual-e5-base`) · optional System One judgments |
| Data | PostgreSQL 16 + pgvector · Alembic raw-SQL migrations |
| Push | ntfy (offline) · in-app notification center · WebSocket `/ws` |
| Sidecars | Playwright browser · isolated workspace (Docker) |
