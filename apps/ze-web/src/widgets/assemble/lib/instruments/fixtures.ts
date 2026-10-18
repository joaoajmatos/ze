import type { WsTraceUpdateFrame } from "@myguyze/ze-client";

type Call = WsTraceUpdateFrame["tool_calls"][number];
type Judgment = NonNullable<WsTraceUpdateFrame["judgments"]>[number];

const call = (over: Partial<Call> & { name: string }): Call => ({
  result_snippet: "",
  duration_ms: 100,
  success: true,
  access: "read",
  ...over,
});
const judgment = (over: Partial<Judgment> & { question_id: string; kind: string }): Judgment => ({
  latency_ms: 300,
  consumed: true,
  ...over,
});

/** The stages of a one-run turn as the server records them, in order of completion. */
export const stages = [
  { name: "preprocess", start_ms: 0, duration_ms: 5, run: 1 },
  { name: "resolve_screen", start_ms: 5, duration_ms: 12, run: 1 },
  { name: "embed_route", start_ms: 17, duration_ms: 40, run: 1 },
  { name: "fetch_context", start_ms: 57, duration_ms: 88, run: 1 },
  { name: "match_skills", start_ms: 145, duration_ms: 30, run: 1 },
  { name: "choose_tier", start_ms: 175, duration_ms: 60, run: 1 },
  { name: "preflight", start_ms: 235, duration_ms: 5, run: 1 },
  { name: "execute_tool", start_ms: 240, duration_ms: 1200, run: 1 },
  { name: "synthesize", start_ms: 1440, duration_ms: 700, run: 1 },
  { name: "record_trace", start_ms: 2140, duration_ms: 4, run: 1 },
  { name: "write_memory", start_ms: 2144, duration_ms: 20, run: 1 },
];

/** A finished trace with most of what the instruments draw. */
export function richTrace(over: Partial<WsTraceUpdateFrame> = {}): WsTraceUpdateFrame {
  return {
    type: "trace_update",
    thread_id: "t1",
    message_id: "m1",
    agent: "companion",
    routing_method: "embedding",
    confidence: 0.72,
    score_gap: 0.18,
    is_compound: true,
    subtasks: ["check goals", "book the room"],
    tool_duration_ms: 4200,
    turn_duration_ms: 6000,
    paused_ms: 0,
    stages,
    usage: {
      main_model: "anthropic/claude-sonnet",
      models: [
        { model: "anthropic/claude-sonnet", calls: 2, prompt_tokens: 9120, completion_tokens: 410, max_prompt_tokens: 5200, cost_usd: 0.0335, estimated: false },
        { model: "anthropic/claude-haiku", calls: 1, prompt_tokens: 800, completion_tokens: 90, max_prompt_tokens: 800, cost_usd: 0.0021, estimated: false },
      ],
      context_fill: 0.026,
      context_window: 200000,
      estimated: false,
      system_one_tokens: 1840,
    },
    telemetry_partial: false,
    memory_chunks: [
      { text: "Runs on Tuesdays", score: 0.91, source: "fact", extraction_confidence: 0.9 },
      { text: "Training for a 5k", score: 0.84, source: "fact", extraction_confidence: 0.7 },
      { text: "Met Ana in May", score: 0.6, source: "episode", extraction_confidence: null },
      { text: "Prefers mornings", score: 0.55, source: "profile", extraction_confidence: 0.5 },
      { text: "Owns a bike", score: 0.4, source: "fact", extraction_confidence: 0.3 },
    ],
    tool_calls: [
      call({ name: "get_goals", duration_ms: 120, agent: "companion", call_index: 0 }),
      call({ name: "delegate_to_agent", duration_ms: 900, access: "delegate", agent: "companion", call_index: 1 }),
      call({ name: "list_events", duration_ms: 200, agent: "calendar", call_index: 2 }),
      call({
        name: "create_event",
        duration_ms: 300,
        access: "write",
        reversibility: "irreversible",
        gate: "approved",
        effect_phrase: "create a calendar event",
        agent: "calendar",
        call_index: 3,
      }),
      call({
        name: "send_email",
        duration_ms: 0,
        access: "write",
        reversibility: "irreversible",
        gate: "denied",
        success: false,
        agent: "messenger",
        call_index: 4,
      }),
    ],
    judgments: [
      judgment({ question_id: "agent", kind: "choice", surface: "routing", bar: { name: "choice_trust", value: 0.5 }, answer: "companion", probabilities: { research: 0.2, companion: 0.7, none: 0.1 }, model: "m-route", input_tokens: 800 }),
      judgment({ question_id: "needs_deep_reasoning", kind: "noul", surface: "complexity", bar: null, answer: 0.2, latency_ms: 150, model: "m-tier", input_tokens: 400 }),
      judgment({ question_id: "commitment", kind: "choice", answer: "reminder", probabilities: { reminder: 0.8, loop: 0.1, none: 0.1 }, latency_ms: 420, model: "m-intake", input_tokens: 900 }),
      judgment({ question_id: "family", kind: "noul", answer: 0.4, latency_ms: 420, model: "m-intake", input_tokens: 900, consumed: false, skip_reason: "invalid_answer" }),
      judgment({ question_id: "intake_outcome", kind: "choice", answer: "link:turn_created:reminder", latency_ms: 420, model: "m-intake", input_tokens: 900 }),
    ],
    tier: { agent: "companion", tier: "full", decided_by: "system_one", model: "anthropic/claude-sonnet" },
    screen: {
      origin: "ask_bar",
      place: "doing",
      subject: ["Goal · Run 5k"],
      resolvers: [
        { kind: "goal", id: "g1", status: "ok", ms: 12 },
        { kind: "loop", id: "l1", status: "missing", ms: 3 },
      ],
    },
    compaction: { span_start: 0, span_end: 6 },
    resume_recap_applied: true,
    rollback: { replaces: "old", entries: [] },
    skills_used: [],
    conductor_hint: null,
    conductor_ledger: [],
    ...over,
  } as WsTraceUpdateFrame;
}
