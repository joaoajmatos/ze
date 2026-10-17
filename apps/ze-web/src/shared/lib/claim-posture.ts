import { humanizeIdentifier } from "./humanize";

export type Posture = "told" | "evidenced" | "inferred" | "suspected" | "goal" | "plain";

const BY_CLAIM_KIND: Record<string, Posture> = {
  identity: "told",
  fact: "evidenced",
  inference: "inferred",
  suspicion: "suspected",
};

const BY_STATE: Record<string, Posture> = {
  suspected: "suspected",
  user_declared: "told",
  causal_guess: "inferred",
  pattern: "inferred",
  tension: "inferred",
  convergence: "inferred",
};

/** Posture from the stored record: the claim kind first, then the owner kind and state. */
export function postureOf(claimKind?: string | null, kind?: string | null, state?: string | null): Posture {
  if (claimKind && BY_CLAIM_KIND[claimKind]) return BY_CLAIM_KIND[claimKind];
  if (kind === "goal") return "goal";
  if (state && BY_STATE[state]) return BY_STATE[state];
  if (kind === "loop" || kind === "hypothesis" || kind === "relationship") return "evidenced";
  return "plain";
}

/** The `.glyph` modifier class: filled told or evidenced, half inferred, dashed suspected, hollow goal. */
export function glyphOf(posture: Posture): string {
  return posture === "inferred" || posture === "suspected" || posture === "goal" ? posture : "";
}

const CHIP: Record<Posture, string> = {
  told: "told",
  evidenced: "evidenced",
  inferred: "inferred",
  suspected: "suspected",
  goal: "goal",
  plain: "noted",
};

export function chipLabelOf(posture: Posture): string {
  return CHIP[posture];
}

const STATE_WORDS: Record<string, string> = {
  awaiting_gate: "waiting on you",
  user_declared: "you told me",
  causal_guess: "my guess at a cause",
  pattern: "a pattern I noticed",
  tension: "two things pulling apart",
  convergence: "things coming together",
  suspected: "I suspect this",
  active: "open",
  drifting: "drifting",
  closed: "done",
  dropped: "dropped",
};

export function stateWords(state: string): string {
  return STATE_WORDS[state] ?? humanizeIdentifier(state).toLowerCase();
}
