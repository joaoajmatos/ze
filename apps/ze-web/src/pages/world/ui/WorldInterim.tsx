import { InterimSections, type InterimSection, type PageLoader } from "@/shared/ui";

type Loaders = { loops: PageLoader; priority: PageLoader };

/** World's interim content; phase 186 replaces this file. The app router supplies the page loaders (pages cannot import pages). */
export function WorldInterim({ loaders, fallback }: { loaders: Loaders; fallback?: React.ReactNode }) {
  const sections: readonly InterimSection[] = [
    { id: "loops", label: "Open loops", path: "/", owns: (p) => p === "/", load: loaders.loops },
    { id: "priority", label: "Priority", path: "/world/priority", owns: (p) => p === "/world/priority", load: loaders.priority },
  ];
  return <InterimSections label="World sections" sections={sections} fallback={fallback} />;
}
