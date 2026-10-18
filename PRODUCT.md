# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

One person. Ze is built for its author and has exactly one user: a solo developer who runs it
self-hosted on their own machine and lives with it daily. They read Ze in a browser on a desktop
and on a phone (the web app has a mobile nav). They are technical and read traces, confidence
values and provenance without needing them softened, but they do not want to do the comparison
work Ze exists to do ("I would have to be the comparison. That is the job I am trying not to do
every morning").

Their jobs with the web app, in order of frequency (inferred from the docs and journal; confirm):

1. Talk to Ze (chat is one input channel, not the product).
2. Glance at what is open, drifting, promised, and what deserves attention now.
3. Answer what Ze needs from them: write approvals, held writes, suspected loops to confirm,
   learnings and procedures to review, goal gates.
4. Check what Ze did on its own (unattended runs, pushes, workflow and goal executions) and why.
5. Inspect and correct what Ze believes: memory, the graph, a reply's trace.

## Product Purpose

Ze is a personal companion with a living model of one person's life at its center: the
world-state. The world-state has four faces: self-model (who Ze is to you), user-model (who you
are), a bounded world-model (the people, projects and events you care about) and active concerns
(what is open, promised, planned or drifting). That model is what lasts; the language model,
agents, persona, storage and orchestration are replaceable organs.

Seven functions cycle around the one world-state: perception, memory, executive function, social
cognition, reflection, action, governance.

The web app exists to make the world-state visible and governable: what is open, drifting and
promised; what Ze noticed; what it did unattended; what needs the user's OK; and how sure Ze is
and why. Success is that the user can see the state of their life as Ze holds it at a glance,
trusts it because every claim shows its kind, source and confidence, and spends attention only
where Ze cannot decide alone.

## Positioning

Ze is not a chat app, an agent harness or a todo list. It is one mind writing to one world-state.
What no neighboring product can truthfully copy:

- Claims have kinds (identity, fact, inference, suspicion, priority), honest provenance, and
  confidence that decays. A claim reaches the user only with the posture its kind licenses: a
  suspicion is shown as a question, never a verdict. Priority orders; it does not make an item
  more true.
- Most of life is not a goal. Lightweight open loops (a promise in a thread, a pending decision,
  a project gone quiet) sit beside heavyweight goals, and one ranked view compares them with
  correlation hypotheses.
- Interruption is a budget. Every discretionary push spends from one shared daily budget, with
  quiet hours.
- Governance asks before anything that cannot be undone, and Retry can undo what a reply did.
- Every reply has a trace: routing, memory used, tools, skills, judgments, model tier.

## Operating Context

- Self-hosted, single user, local machine; pre-v1. FastAPI + LangGraph backend, React web client
  over REST (`/api/v0`) and one WebSocket (`/ws`). Push via ntfy when the web app is closed.
- The world-state changes without the user: proactive jobs, drift sweeps, nightly consolidation
  and dream passes, workflows and goals running unattended. The web app should reflect that live
  (WS frames: `trace_update`, `notification`, `confirm_request`, `message_rollback`).
- Plugins contribute UI at runtime through `GET /api/v0/ui/manifest` as server-driven primitives
  from `@myguyze/ze-ui`: modules in place slots, Ask presets and settings sections, never pages
  (see Plugin UI model).
- English and Portuguese both appear in conversation; the web UI chrome is English.

## Capabilities and Constraints

- Data the backend exposes today: chat sessions and messages with per-message traces and
  feedback; priority snapshot (loops, goals, hypotheses, relationships, with user overrides and
  `sources_failed`); open loops (suspected → active → drifting → closed | dropped) with sources,
  confidence and linked reminders/goals; goals with milestones, gates, traces and learnings;
  workflows with executions and revisions; held writes; notifications and quiet hours; memory
  feed, timeline bounds, activity, graph and entity detail; procedures and candidates; skills;
  workspace files and runs; costs summary and anomalies; data domains,
  export/import/delete.
- Not exposed over REST today (would need a backend ask): correlation hypotheses as a list (only
  inside the priority snapshot), the action-record ledger, contribution collisions, routing log,
  push log / proactive job runs, the interruption budget remaining today.
- Constraints: Feature-Sliced Design in `apps/ze-web` (pages → widgets → features → entities →
  shared, lint-enforced); backend types only from `@myguyze/ze-client`; server-driven UI through
  `@myguyze/ze-ui`. Pre-v1: break and replace rather than shim.
- Terminology to keep: "trace" (the chat side panel, not "Ze's Mind"), "open loops", "priority",
  "goals", "workflows", "procedures", "skills", "workspace", "held writes", "quiet hours".
- Undecided: whether the home screen is a dashboard or chat (this reimagine proposes a dashboard
  home; to be confirmed by the user's pick).

## Brand Commitments

- Name: Ze. Ze is a lifelong companion, not a product launch. No finale framing.
- Voice: short sentences, active voice, concrete before abstract, American spelling. No "delve",
  "robust", "seamless", "unlock". Ze uses what it knows silently and does not recite it.
- The user-facing interface is the web app. Never describe Telegram-style capabilities.
- A static AI disclosure is shown in chat (phase 117).
- Do not duplicate page titles already shown in the top bar.

## Evidence on Hand

- Real seeded dev data via `core/ops/ze-seed` (narrative fixtures, `seed-dev-*` namespace).
- Screenshots in `docs/assets/` (chat-trace, loops, priority, goals).
- Diagrams in `docs/diagrams/` (world-state spine, cognitive loop, claim ladder).
- No user testimonials, metrics or usage numbers exist; do not invent any.

## Product Principles

1. The world-state is the subject of every screen. A screen earns its place by answering a
   question about what Ze holds, does, or needs; a list of rows is not a purpose.
2. Show the claim's posture. Kind, source and confidence travel with every claim; suspicions are
   asked, not stated; confidence ages visibly.
3. Attention is scarce. Lead with what needs the user's decision and what changed; everything
   else is one step away, ranked, not spread across equal tiles.
4. Unattended work is accountable. What Ze did on its own, and why, is always findable from the
   thing it touched.
5. Organs churn, functions persist. Group by the function a screen serves, not by package.

## Plugin UI model

Agreed with the user on 2026-10-18 (phases 191a and 191b).

1. Plugins are sources of data and behaviour. They feed the core contracts: claims, loops,
   signals, actions, screen resolvers, composed answers and presets, and settings. The five places
   render what they feed. Most plugins need no UI of their own.
2. A plugin contributes modules, never pages. A module is a title, a data source and a layout of
   primitives, bound to a slot a place offers: a Mind entity facet, a Doing run block, a
   Governance › Connections card, an Ask preset chip. The place owns placement, density and design.
3. Primitives are server-driven descriptors from `@myguyze/ze-ui` and `ze-components`. No plugin
   script runs in the browser. A new visual is a reviewed, named primitive added to `ze-ui`; an
   unknown type renders as a plain table. Claim posture is set by code.
4. A plugin's full view is a composed answer in Ask, summoned by a preset chip.
5. Actions on a screen are typed and run through the same gates as chat: an irreversible change
   asks first.

## Accessibility & Inclusion

No product-specific requirement recorded beyond the phase 117 fixes (accessible names on nav,
keyboard-reachable chat). Treat WCAG 2.2 AA as the floor and honor reduced motion (open: confirm).
