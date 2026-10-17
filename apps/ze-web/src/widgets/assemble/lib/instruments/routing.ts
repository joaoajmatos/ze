import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { places } from "@/shared/config";

export const METHOD_WORDS: Record<string, string> = {
  embedding: "matched by meaning",
  haiku: "chosen by a model",
  fallback: "fell back to the default",
  screen: "from the screen you asked about",
  open_query: "an open-items question",
  preset: "a preset question",
  forced: "set by the caller",
};

export interface RoutingBar {
  label: string;
  /** 0..1, or null for a fixed route (nothing was scored). */
  value: number | null;
  /** The runner-up's score, only where the trace supports it. */
  ghost: number | null;
}

export interface RoutingOption {
  name: string;
  probability: number;
  chosen: boolean;
}

export interface RoutingView {
  methodWords: string;
  bar: RoutingBar | null;
  options: RoutingOption[];
  tierLine: string | null;
}

const FIXED = new Set(["screen", "preset", "forced", "open_query"]);
const ROUTING_QUESTIONS = new Set(["agent", "multi_specialist"]);

/** The bar is labelled by what produced it. Nothing is drawn that the trace did not measure. */
export function routingFor(trace: Partial<WsTraceUpdateFrame>): RoutingView {
  const method = trace.routing_method ?? "";
  const judgments = trace.judgments ?? [];
  const confidence = trace.confidence ?? 0;
  const agentConsumed = judgments.some((j) => j.question_id === "agent" && j.consumed !== false);

  let bar: RoutingBar | null;
  if (FIXED.has(method)) bar = { label: "fixed", value: null, ghost: null };
  else if (method === "fallback" || method === "") bar = null;
  else if (method === "haiku") bar = { label: "E5 score of the pick", value: confidence, ghost: null };
  else if (agentConsumed) bar = { label: "Choice confidence", value: confidence, ghost: null };
  else bar = { label: "E5 score", value: confidence, ghost: Math.max(0, confidence - (trace.score_gap ?? 0)) };

  const routing = judgments.find((j) => ROUTING_QUESTIONS.has(j.question_id) && j.probabilities);
  const options = Object.entries(routing?.probabilities ?? {})
    .map(([name, probability]) => ({ name, probability, chosen: routing?.answer === name }))
    .sort((a, b) => b.probability - a.probability);

  const tier = trace.tier;
  const tierLine = tier ? `${tier.tier} · ${tier.decided_by === "system_one" ? "System One" : tier.decided_by.replace(/_/g, " ")} · ${tier.model}` : null;
  return { methodWords: METHOD_WORDS[method] ?? method, bar, options, tierLine };
}

const PLACE_LABEL: Record<string, string> = Object.fromEntries(places.map((p) => [p.id, p.label]));

/** "Asked from · Doing › subject" or "Asked about · subject"; null when the turn carried no screen. */
export function coordinateOf(trace: Partial<WsTraceUpdateFrame>): string | null {
  const screen = trace.screen;
  if (!screen) return null;
  const subject = screen.subject?.[0];
  if (screen.origin === "chat_about" && subject) return `Asked about · ${subject}`;
  const place = screen.place ? (PLACE_LABEL[screen.place] ?? screen.place) : null;
  const where = [place, subject].filter(Boolean).join(" › ");
  return where ? `Asked from · ${where}` : null;
}
