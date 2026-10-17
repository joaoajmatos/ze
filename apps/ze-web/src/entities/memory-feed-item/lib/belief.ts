import type { MemoryFeedItem, WsScreenRef } from "@myguyze/ze-client";
import { dayMonth } from "@/shared/lib/clock-format";

const FALLBACK = "A fact Ze holds";

function humanisePredicate(key: string): string {
  const spaced = key.replace(/[_-]+/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function isSentence(value: string): boolean {
  const words = value.trim().split(/\s+/);
  return words.length >= 3 && /^\p{Ll}/u.test(words[0]);
}

/** One plain sentence for a stored fact; the raw predicate key never renders. */
export function beliefSentence(key: string | null | undefined, value: string | null | undefined): string {
  const v = (value ?? "").trim();
  if (!v) return FALLBACK;
  if (isSentence(v)) return v;
  const k = (key ?? "").trim();
  return k ? `${humanisePredicate(k)} ${v}` : v;
}

export function sinceLabel(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const days = Math.floor((now.getTime() - then.getTime()) / 86_400_000);
  if (days < 1 && then.getUTCDate() === now.getUTCDate()) return "since today";
  if (days <= 1) return "since yesterday";
  if (days < 30) return `since ${days} days ago`;
  return `since ${dayMonth(then)}`;
}

const PROVENANCE: Record<string, string> = {
  raw: "you told me",
  synthesized: "I worked it out",
  graph_recall: "from what I already knew",
  live_search: "from a web search",
  prompt_supplied: "from what you gave me",
};

export function sourceWords(provenance: string | null | undefined, agent: string | null | undefined): string {
  const from = provenance ? (PROVENANCE[provenance] ?? provenance.replace(/_/g, " ")) : "";
  const via = agent ? `via ${agent.replace(/[_-]+/g, " ")}` : "";
  return [from, via].filter(Boolean).join(", ");
}

/** The screen reference for a belief shown as a row. */
export function factRef(item: Pick<MemoryFeedItem, "id" | "key" | "value">): WsScreenRef {
  return { kind: "fact", id: item.id, label: beliefSentence(item.key, item.value), component: "belief_row" };
}
