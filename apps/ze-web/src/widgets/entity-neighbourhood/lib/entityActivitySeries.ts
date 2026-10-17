import type { EntityDetailResponse } from "@myguyze/ze-client";
import type { ChartPoint } from "@myguyze/ze-ui/charts";

function dayBucket(value: string): string {
  return value.slice(0, 10);
}

export function entityActivitySeries(detail: EntityDetailResponse): ChartPoint[] {
  const factsByDay = new Map<string, number>();
  const episodesByDay = new Map<string, number>();

  for (const fact of detail.facts) {
    if (!fact.created_at) continue;
    const day = dayBucket(fact.created_at);
    factsByDay.set(day, (factsByDay.get(day) ?? 0) + 1);
  }
  for (const episode of detail.episodes) {
    const day = dayBucket(episode.created_at);
    episodesByDay.set(day, (episodesByDay.get(day) ?? 0) + 1);
  }

  const days = [...new Set([...factsByDay.keys(), ...episodesByDay.keys()])].sort();
  const points: ChartPoint[] = [];
  for (const day of days) {
    const facts = factsByDay.get(day) ?? 0;
    const episodes = episodesByDay.get(day) ?? 0;
    if (facts > 0) points.push({ x: day, y: facts, series: "fact" });
    if (episodes > 0) points.push({ x: day, y: episodes, series: "episode" });
  }
  return points;
}
