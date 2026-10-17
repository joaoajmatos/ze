import type { Concern, Decision, World } from "./world";

export type PaletteId = "ultraviolet" | "amethyst" | "orchid";
export type OrbState = "idle" | "listening" | "thinking" | "speaking" | "assembling" | "attention" | "acting" | "done" | "error";

/** The three palettes' leads, ultraviolet → amethyst → orchid; the orb blends them in oklab in some phases. */
export const TONES: [string, string, string] = ["#9e82ff", "#c08cff", "#b9a3ff"];

export const PALETTES: { id: PaletteId; name: string; note: string }[] = [
  { id: "orchid", name: "Orchid", note: "pale lavender on warm plum" },
  { id: "ultraviolet", name: "Ultraviolet", note: "cool violet on near-black indigo" },
  { id: "amethyst", name: "Amethyst", note: "magenta-leaning purple on violet-black" },
];

export const ORB_STATES: { id: OrbState; note: string }[] = [
  { id: "idle", note: "breathing; a ripple crosses the sphere, the limb wobbles" },
  { id: "listening", note: "gathers and leans toward the Ask field; a ring runs inward" },
  { id: "thinking", note: "slow internal swirl under a scanning light" },
  { id: "speaking", note: "pulses with the voice; waveform across the equator" },
  { id: "assembling", note: "a few dots thrown out along their spokes and pulled back" },
  { id: "attention", note: "coral flare from the core on a two-beat heart; limb bulges" },
  { id: "acting", note: "working arc on the belt plus one faint orbit ring per run" },
  { id: "done", note: "one bloom outward, then settles" },
  { id: "error", note: "dim, flickering, jittering; coral limb" },
];

/** Claim posture for the honesty visuals: solid = told, dotted = inferred or suspected. */
export type Posture = "told" | "evidenced" | "inferred" | "suspected";

export function kindLabelOf(c: Concern): string {
  return { loop: "loop", goal: "goal", hypothesis: "inference", relationship: "person" }[c.kind] ?? c.kind;
}

export function postureOf(c: Concern): Posture {
  if (c.state === "suspected") return "suspected";
  if (c.kind === "hypothesis" || c.provenance === "correlation") return "inferred";
  if (c.provenance === "user_declared") return "told";
  return "evidenced";
}




export function daysSince(d: Date | null, now: Date): number | null {
  if (!d) return null;
  return Math.max(0, Math.round((now.getTime() - d.getTime()) / 86400_000));
}

export function daysUntil(d: Date | null, now: Date): number | null {
  if (!d) return null;
  return Math.round((d.getTime() - now.getTime()) / 86400_000);
}

export interface Slip {
  concern: Concern;
  kind: "slipped" | "at_risk";
  why: string;
  /** Days past the drift deadline, or days since the last evidence when there is none. */
  overdueDays: number | null;
  overdueLabel: "past deadline" | "quiet for";
}

/** What is slipping: drifting loops, then active loops Ze has a drift rationale for. */
export function slipsOf(world: World): Slip[] {
  const out: Slip[] = [];
  for (const c of world.concerns) {
    if (c.state === "drifting") {
      out.push({
        concern: c,
        kind: "slipped",
        why: c.driftRationale ?? "No new evidence since it went quiet",
        overdueDays: c.due ? Math.max(0, -(daysUntil(c.due, world.now) ?? 0)) : daysSince(c.updatedAt, world.now),
        overdueLabel: c.due ? "past deadline" : "quiet for",
      });
    }
  }
  for (const c of world.concerns) {
    if (c.state === "active" && c.driftRationale) {
      out.push({ concern: c, kind: "at_risk", why: c.driftRationale, overdueDays: null, overdueLabel: "quiet for" });
    }
  }
  return out;
}


/** Ze's one sentence for the main view, derived from the world, never generated. */
export function worldSentence(world: World): string {
  const slips = slipsOf(world);
  const slipped = slips.filter((s) => s.kind === "slipped");
  const gates = world.goals.filter((g) => g.openGate);
  const parts: string[] = [];
  if (slipped.length === 1) parts.push(`One promise is slipping: “${short(slipped[0].concern.title)}”.`);
  else if (slipped.length > 1) {
    const longest = [...slipped].sort((a, b) => (b.overdueDays ?? 0) - (a.overdueDays ?? 0))[0];
    parts.push(`${cap(words(slipped.length))} promises are slipping; “${short(longest.concern.title)}” has been quiet longest.`);
  }
  else parts.push("Nothing is slipping right now.");
  if (gates.length) parts.push(`${gates[0].title} is waiting on your OK.`);
  const sus = world.concerns.filter((c) => c.state === "suspected").length;
  if (sus) parts.push(`I'm holding ${words(sus)} suspicion${sus > 1 ? "s" : ""} until you confirm ${sus > 1 ? "them" : "it"}.`);
  return parts.join(" ");
}

/** Ze's answer to "what's slipping?", derived from the world. */
export function slippingAnswer(world: World): { headline: string; sentence: string; offer: string | null; target: Concern | null } {
  const slips = slipsOf(world);
  const slipped = slips.filter((s) => s.kind === "slipped");
  const risk = slips.filter((s) => s.kind === "at_risk");
  const headline = `${slipped.length} SLIPPING · ${risk.length} AT RISK`;
  const s: string[] = [];
  if (slipped.length) {
    s.push(`${cap(words(slipped.length))} promise${slipped.length > 1 ? "s" : ""} slipped.`);
    for (const x of slipped) s.push(`“${short(x.concern.title)}”: ${lower(x.why)}.`);
  } else s.push("Nothing has slipped.");
  if (risk.length) s.push(`“${short(risk[0].concern.title)}” is ${lower(risk[0].why)}.`);
  const target = [...slipped].sort((a, b) => (b.overdueDays ?? 0) - (a.overdueDays ?? 0))[0];
  const offer = target ? `Want me to draft the next step on “${short(target.concern.title)}” tonight?` : null;
  return { headline, sentence: s.join(" "), offer, target: target?.concern ?? null };
}

export function decisionsFor(world: World): Decision[] {
  return world.decisions.slice(0, 4);
}

function cap(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
function lower(s: string): string {
  return s.charAt(0).toLowerCase() + s.slice(1).replace(/\.$/, "");
}
function words(n: number): string {
  return ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"][n] ?? String(n);
}
/** The part of a loop title before a colon, trimmed to a readable length. */
export function short(title: string): string {
  const t = title.split(":")[0].trim();
  return t.length > 60 ? `${t.slice(0, 58).trim()}…` : t;
}
