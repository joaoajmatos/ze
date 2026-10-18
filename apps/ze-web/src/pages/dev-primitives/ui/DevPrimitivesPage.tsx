import { parsePrimitiveTree, type PrimitiveTree } from "@myguyze/ze-ui";
import { PrimitiveTreeRenderer, type PrimitiveRendererActions } from "@myguyze/ze-ui/react";
import { useMemo, useState } from "react";
import { HUD_CLASS_NAMES, renderHudHeadline } from "@/features/primitive-tree";

interface Expectation {
  client: unknown;
}

const trees = import.meta.glob("../../../../../../packages/ze-ui/fixtures/*.json", {
  eager: true,
  import: "default",
}) as Record<string, unknown>;

interface Fixture {
  name: string;
  /** The primitive type the fixture shows: the file name up to its first dash. */
  type: string;
  tree: PrimitiveTree;
}

const fileName = (path: string) => path.slice(path.lastIndexOf("/") + 1).replace(/\.json$/, "");

function loadFixtures(): Fixture[] {
  const fixtures: Fixture[] = [];
  for (const [path, data] of Object.entries(trees)) {
    const name = fileName(path);
    if (name.endsWith(".expect")) continue;
    const expectation = trees[path.replace(/\.json$/, ".expect.json")] as Expectation | undefined;
    if (expectation?.client !== "valid") continue;
    fixtures.push({ name, type: name.split("-")[0], tree: parsePrimitiveTree(data) });
  }
  return fixtures.sort((a, b) => a.name.localeCompare(b.name));
}

function groupByType(fixtures: Fixture[]): [string, Fixture[]][] {
  const groups = new Map<string, Fixture[]>();
  for (const fixture of fixtures) groups.set(fixture.type, [...(groups.get(fixture.type) ?? []), fixture]);
  return [...groups.entries()];
}

/** The primitive vocabulary at a glance (development only): every valid fixture, wide and at phone width. */
export function DevPrimitivesPage() {
  const [last, setLast] = useState<string | null>(null);
  const groups = useMemo(() => groupByType(loadFixtures()), []);
  const actions = useMemo<PrimitiveRendererActions>(
    () => ({
      classNames: HUD_CLASS_NAMES,
      renderHeadline: renderHudHeadline,
      onAction: (action) => {
        setLast(JSON.stringify(action));
        return true;
      },
      onFormSubmit: () => true,
      onCardAction: () => true,
    }),
    [],
  );

  return (
    <div className="px-4 py-6 max-w-5xl mx-auto" style={{ display: "grid", gap: 32 }}>
      <header>
        <h1 className="pr-heading">Primitives</h1>
        <p className="pr-caption">Actions are shown here, never run.</p>
        <p role="status" className="pr-code" style={{ minHeight: 24 }}>
          {last ?? ""}
        </p>
      </header>
      {groups.map(([type, fixtures]) => (
        <section key={type} aria-label={type} style={{ display: "grid", gap: 16 }}>
          <h2 className="pr-sub">{type}</h2>
          {fixtures.map((fixture) => (
            <div key={fixture.name} style={{ display: "grid", gap: 8 }}>
              <p className="pr-caption">{fixture.name}</p>
              <div data-testid="frame-natural">
                <PrimitiveTreeRenderer nodes={fixture.tree} actions={actions} />
              </div>
              <div data-testid="frame-390" style={{ width: 390, maxWidth: "100%", border: "1px dashed var(--hair)", padding: 8 }}>
                <PrimitiveTreeRenderer nodes={fixture.tree} actions={actions} />
              </div>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
