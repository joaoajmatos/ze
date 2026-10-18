/** The shared fixtures in `packages/ze-ui/fixtures`, keyed by name (`button`, `table-keyed`, …). */
export interface FixtureExpect {
  version?: string | null;
  client: "valid" | "tolerated" | "legacy" | { invalid_at: string };
}

const trees = import.meta.glob<{ default: unknown }>("../../fixtures/*.json", { eager: true });

function nameOf(path: string): string {
  return path.replace(/^.*\//, "").replace(/\.json$/, "");
}

export const fixtureNames: string[] = Object.keys(trees)
  .map(nameOf)
  .filter((n) => n.endsWith(".expect"))
  .map((n) => n.replace(/\.expect$/, ""))
  .sort();

export function fixture(name: string): unknown {
  const entry = Object.entries(trees).find(([path]) => nameOf(path) === name);
  if (!entry) throw new Error(`No fixture named ${name}`);
  return entry[1].default;
}

export function fixtureExpect(name: string): FixtureExpect {
  return fixture(`${name}.expect`) as FixtureExpect;
}
