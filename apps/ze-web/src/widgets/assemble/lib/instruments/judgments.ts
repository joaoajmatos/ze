import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { humanizeStatus } from "@/shared/lib";

type Judgment = NonNullable<WsTraceUpdateFrame["judgments"]>[number];

export type Surface = "routing" | "tier" | "skills" | "intake" | "other";

const SURFACE_OF: Record<string, Surface> = {
  agent: "routing",
  multi_specialist: "routing",
  needs_deep_reasoning: "tier",
  skill: "skills",
  needs_skill: "skills",
  commitment: "intake",
  family: "intake",
  biography: "intake",
  is_open_concern: "intake",
  explicit_declaration: "intake",
  resolves_existing: "intake",
};

const LABEL_OF: Record<string, string> = {
  agent: "Which specialist",
  multi_specialist: "More than one specialist",
  needs_deep_reasoning: "Needs deep reasoning",
  skill: "Which skill",
  needs_skill: "Needs a skill",
  commitment: "What kind of commitment",
  family: "Kind of fact",
  biography: "About you",
  is_open_concern: "An open concern",
  explicit_declaration: "Said outright",
  resolves_existing: "Settles an open loop",
};

const SURFACE_LABEL: Record<Surface, string> = {
  routing: "Routing",
  tier: "Tier",
  skills: "Skills",
  intake: "What Ze kept",
  other: "Other",
};

const SKIP_WORDS: Record<string, string> = {
  error: "the request failed",
  invalid_answer: "the model's answer was not usable",
  overload: "the model was overloaded",
  timeout: "the model took too long",
  uncalibrated: "the judgment is not calibrated yet",
};

export interface JudgmentRow {
  id: string;
  label: string;
  shape: "choice" | "noul" | "score";
  answer: string | null;
  /** Noul probability of yes, or a Score value. */
  value: number | null;
  options: { name: string; probability: number }[];
  status: "used" | "skipped";
  reason: string | null;
  surface: string | null;
  /** The bar the answer was held against; null when the surface has none yet. */
  bar: { name: string; value: number } | null;
  /** The surface exists but ships without a calibrated bar. */
  uncalibrated: boolean;
}

export interface JudgmentGroup {
  surface: Surface;
  label: string;
  rows: JudgmentRow[];
}

export interface IntakeOutcome {
  kind: string;
  reason: string;
  link: string | null;
  words: string;
}

const OUTCOME_WORDS: Record<string, (link: string | null) => string> = {
  persist_fact: () => "kept as a fact",
  resolve_loop: () => "closed an open loop",
  create_loop_declared: () => "started tracking what you asked it to",
  create_loop_suspected: () => "noted a concern it suspects you have",
  link: (link) => `linked to the ${link ?? "record"} it created this turn`,
  hold: () => "held, nothing written",
  fallback: () => "used the older extractor",
};

const PLAIN_HOLD = new Set(["waiting_on", "trivial", "unsure"]);

/** `intake_outcome` carries `<kind>:<reason>[:<link>]`; this puts it into words. */
export function describeIntakeOutcome(answer: string | number | null | undefined): IntakeOutcome | null {
  if (typeof answer !== "string" || !answer) return null;
  const [kind, reason = "", link = null] = answer.split(":");
  const make = OUTCOME_WORDS[kind];
  let words: string;
  if (!make) words = `${kind.replace(/_/g, " ")}${reason ? ` (${reason.replace(/_/g, " ")})` : ""}`;
  else if (kind === "hold" && reason && !PLAIN_HOLD.has(reason)) words = `${make(link)} (${reason.replace(/_/g, " ")})`;
  else words = make(link);
  return { kind, reason, link, words };
}

function rowOf(j: Judgment): JudgmentRow {
  const shape = j.kind === "choice" ? "choice" : j.kind === "score" ? "score" : "noul";
  const options = Object.entries(j.probabilities ?? {})
    .map(([name, probability]) => ({ name, probability }))
    .sort((a, b) => b.probability - a.probability);
  const skipped = j.consumed === false;
  return {
    id: j.question_id,
    label: LABEL_OF[j.question_id] ?? humanizeStatus(j.question_id),
    shape,
    answer: shape === "choice" && j.answer != null ? String(j.answer) : null,
    value: shape !== "choice" && typeof j.answer === "number" ? j.answer : null,
    options,
    status: skipped ? "skipped" : "used",
    surface: j.surface ?? null,
    bar: j.bar ?? null,
    uncalibrated: Boolean(j.surface) && !j.bar,
    reason: skipped ? (SKIP_WORDS[j.skip_reason ?? ""] ?? (j.skip_reason ? humanizeStatus(j.skip_reason).toLowerCase() : "not used")) : null,
  };
}

export function describeJudgments(judgments: Judgment[] | undefined): { groups: JudgmentGroup[]; outcome: IntakeOutcome | null } {
  const list = judgments ?? [];
  const outcomeRow = list.find((j) => j.question_id === "intake_outcome");
  const outcome = describeIntakeOutcome(outcomeRow?.answer);
  const groups = new Map<Surface, JudgmentRow[]>();
  for (const j of list) {
    if (j.question_id === "intake_outcome") continue;
    const surface = SURFACE_OF[j.question_id] ?? "other";
    groups.set(surface, [...(groups.get(surface) ?? []), rowOf(j)]);
  }
  const order: Surface[] = ["routing", "tier", "skills", "intake", "other"];
  return {
    groups: order.filter((s) => groups.has(s)).map((s) => ({ surface: s, label: SURFACE_LABEL[s], rows: groups.get(s)! })),
    outcome,
  };
}
