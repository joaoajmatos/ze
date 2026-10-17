import type { MemoryFeedItem } from "@myguyze/ze-client";
import { short, slipsOf, slippingAnswer, type Slip } from "./hud";
import type { Concern, Decision, GoalView, WorkflowView, World } from "./world";

export type QuestionKind = "slipping" | "ledgerlite" | "decide" | "unknown";

export const PRESETS: { q: string; kind: QuestionKind }[] = [
  { q: "what's slipping?", kind: "slipping" },
  { q: "how is the LedgerLite launch going?", kind: "ledgerlite" },
  { q: "what should I decide today?", kind: "decide" },
];

export function parseQuestion(q: string): QuestionKind {
  const t = q.toLowerCase();
  if (/ledgerlite|launch|product hunt/.test(t)) return "ledgerlite";
  if (/decid|approve|confirm|needs me|should i/.test(t)) return "decide";
  if (/slip|late|overdue|behind|drift|stuck/.test(t)) return "slipping";
  return "unknown";
}

export type Span = 4 | 6 | 8 | 12;

export type Component =
  | { id: string; kind: "sentence"; span: Span; sentence: string; offer: string | null; target: Concern | null; note?: string }
  | { id: string; kind: "timeline"; span: Span; title: string; items: Concern[] }
  | { id: string; kind: "evidence"; span: Span; slip: Slip }
  | { id: string; kind: "loop"; span: Span; concern: Concern }
  | { id: string; kind: "person"; span: Span; person: World["people"][number]; linked: Concern[] }
  | { id: string; kind: "goal"; span: Span; goal: GoalView }
  | { id: string; kind: "workflow"; span: Span; workflow: WorkflowView }
  | { id: string; kind: "decision"; span: Span; decision: Decision }
  | { id: string; kind: "chart"; span: Span; title: string; series: { label: string; value: number; ok: boolean }[]; unit: string }
  | { id: string; kind: "facts"; span: Span; title: string; facts: MemoryFeedItem[] };

export interface Composition {
  kind: QuestionKind;
  headline: string;
  components: Component[];
}

function personNamed(world: World, title: string) {
  return world.people.find((p) => {
    const first = p.name.split(" ")[0];
    return first.length > 2 && title.includes(first);
  });
}

/** Ze picks the components a question needs and lays them out. Derived from the world, never generated. */
export function compose(question: string, world: World): Composition {
  const kind = parseQuestion(question);
  switch (kind) {
    case "ledgerlite":
      return composeTopic(world, /ledgerlite|product hunt|launch|beta|landing page/i, "LedgerLite");
    case "decide":
      return composeDecide(world);
    case "unknown":
      return { ...composeSlipping(world), kind: "unknown" };
    default:
      return composeSlipping(world);
  }
}

function composeSlipping(world: World): Composition {
  const slips = slipsOf(world);
  const answer = slippingAnswer(world);
  const slipped = slips.filter((s) => s.kind === "slipped");
  const risk = slips.filter((s) => s.kind === "at_risk");
  const timelineItems = world.concerns.filter((c) => c.due || c.state === "drifting");
  const components: Component[] = [];
  components.push({ id: "timeline", kind: "timeline", span: 12, title: "Slip timeline · past 7 days to next 7", items: timelineItems });
  for (const s of slipped) components.push({ id: `ev:${s.concern.id}`, kind: "evidence", span: 4, slip: s });
  for (const s of risk) components.push({ id: `ev:${s.concern.id}`, kind: "evidence", span: 4, slip: s });
  const longest = [...slipped].sort((a, b) => (b.overdueDays ?? 0) - (a.overdueDays ?? 0))[0];
  const p = longest ? personNamed(world, longest.concern.title) : undefined;
  if (p) components.push({ id: `person:${p.id}`, kind: "person", span: 4, person: p, linked: world.concerns.filter((c) => c.title.includes(p.name.split(" ")[0])) });
  components.push({ id: "sentence", kind: "sentence", span: p ? 8 : 12, sentence: answer.sentence, offer: answer.offer, target: answer.target });
  return { kind: "slipping", headline: answer.headline, components };
}

function composeTopic(world: World, re: RegExp, name: string): Composition {
  const loops = world.concerns.filter((c) => re.test(c.title));
  const goals = world.goals.filter((g) => re.test(g.title) || re.test(g.objective));
  const wfs = world.workflows.filter((w) => re.test(w.name));
  const facts = world.facts.filter((f) => re.test(`${f.key} ${f.value ?? ""}`)).slice(0, 5);
  const slipped = loops.filter((c) => c.state === "drifting");
  const hyps = loops.filter((c) => c.kind === "hypothesis");
  const components: Component[] = [];
  const s: string[] = [];
  if (slipped.length) s.push(`${cap(words(slipped.length))} ${name} promise${slipped.length > 1 ? "s" : ""} slipped: ${slipped.map((c) => `“${short(c.title)}”${c.driftRationale ? ` (${lower(c.driftRationale)})` : ""}`).join("; ")}.`);
  else if (loops.length) s.push(`Nothing about ${name} has slipped.`);
  else s.push(`I hold nothing open about ${name}.`);
  const offWfs = wfs.filter((w) => !w.enabled);
  if (wfs.length) s.push(`${cap(words(wfs.length))} workflow${wfs.length > 1 ? "s touch" : " touches"} it${offWfs.length ? `, ${offWfs.length === wfs.length ? (wfs.length > 1 ? "all" : "and it is") : words(offWfs.length)} switched off (${offWfs.map((w) => w.name).join(", ")})` : ""}.`);
  if (hyps.length) s.push(`I suspect ${hyps.map((h) => `${h.title.replace(/\.$/, "")} (a hypothesis at ${Math.round((h.confidence ?? 0) * 100)}%)`).join("; ")}, but I have not confirmed it.`);
  const target = slipped[0] ?? null;
  for (const c of loops.filter((c) => c.kind !== "hypothesis")) components.push({ id: `loop:${c.id}`, kind: "loop", span: 4, concern: c });
  for (const g of goals) components.push({ id: `goal:${g.id}`, kind: "goal", span: 8, goal: g });
  for (const w of wfs) components.push({ id: `wf:${w.id}`, kind: "workflow", span: 4, workflow: w });
  const runs = wfs.flatMap((w) => w.runs.map((r) => ({ label: w.name, value: r.durationMs ? Math.round(r.durationMs / 1000) : 1, ok: r.ok })));
  if (runs.length >= 3) components.push({ id: "chart", kind: "chart", span: 4, title: `${name} workflow runs · seconds`, series: runs.slice(-14), unit: "s" });
  for (const h of hyps) components.push({ id: `loop:${h.id}`, kind: "loop", span: 4, concern: h });
  if (facts.length) components.push({ id: "facts", kind: "facts", span: 8, title: `What I know about ${name}`, facts });
  components.push({ id: "sentence", kind: "sentence", span: 12, sentence: s.join(" "), offer: target ? `Want me to draft a note to settle “${short(target.title).replace(/^Decide (the )?/, "")}” tonight?` : null, target });
  return { kind: "ledgerlite", headline: `${name.toUpperCase()} · ${slipped.length} SLIPPED · ${wfs.length} WORKFLOWS`, components };
}

function composeDecide(world: World): Composition {
  const decisions = world.decisions;
  const gates = decisions.filter((d) => d.kind === "gate");
  const sus = decisions.filter((d) => d.kind === "suspicion");
  const held = decisions.filter((d) => d.kind === "held_write");
  const components: Component[] = [];
  for (const d of held) components.push({ id: `dec:${d.id}`, kind: "decision", span: 6, decision: d });
  for (const d of gates) {
    const g = world.goals.find((x) => `gate:${x.id}` === d.id);
    if (g) components.push({ id: `goal:${g.id}`, kind: "goal", span: 8, goal: g });
    else components.push({ id: `dec:${d.id}`, kind: "decision", span: 6, decision: d });
  }
  for (const d of sus) components.push({ id: `dec:${d.id}`, kind: "decision", span: 4, decision: d });
  const n = held.length + gates.length + sus.length;
  const s: string[] = [];
  if (n === 0) s.push("Nothing waits on you today. I can carry the rest.");
  else {
    const parts: string[] = [];
    if (held.length) parts.push(`${words(held.length)} write${held.length > 1 ? "s" : ""} held for your OK`);
    if (gates.length) parts.push(`${words(gates.length)} goal gate${gates.length > 1 ? "s" : ""}`);
    if (sus.length) parts.push(`whether I keep tracking ${words(sus.length)} suspicion${sus.length > 1 ? "s" : ""}`);
    s.push(`${cap(words(n))} thing${n > 1 ? "s" : ""} only you can decide today: ${parts.join(", ")}.`);
    s.push("Everything else I can carry without you.");
  }
  components.push({ id: "sentence", kind: "sentence", span: 12, sentence: s.join(" "), offer: null, target: null });
  return { kind: "decide", headline: `${n} TO DECIDE · ${world.budget.max - world.budget.spent} PUSHES LEFT`, components };
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
