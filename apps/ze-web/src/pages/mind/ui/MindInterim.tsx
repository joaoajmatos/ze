import { InterimSections, type InterimSection, type PageLoader } from "@/shared/ui";

type Loaders = { memory: PageLoader; graph: PageLoader };

/** Mind's interim content; phase 189 replaces this file. Memory is the index. */
export function MindInterim({ loaders, fallback }: { loaders: Loaders; fallback?: React.ReactNode }) {
  const sections: readonly InterimSection[] = [
    { id: "memory", label: "Memory", path: "/mind", owns: (p) => p === "/mind", load: loaders.memory },
    { id: "graph", label: "Graph", path: "/mind/graph", owns: (p) => p === "/mind/graph", load: loaders.graph },
  ];
  return <InterimSections label="Mind sections" sections={sections} fallback={fallback} />;
}
