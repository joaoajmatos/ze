import { InterimSections, type InterimSection, type PageLoader } from "@/shared/ui";

type Loaders = { goals: PageLoader; workflows: PageLoader; skills: PageLoader };

const under = (base: string) => (p: string) => p === base || p.startsWith(`${base}/`);

/** Doing's interim content; phase 188 replaces this file. Goals is the index. */
export function DoingInterim({ loaders, fallback }: { loaders: Loaders; fallback?: React.ReactNode }) {
  const sections: readonly InterimSection[] = [
    { id: "goals", label: "Goals", path: "/doing/goals", owns: (p) => p === "/doing" || under("/doing/goals")(p), load: loaders.goals },
    { id: "workflows", label: "Workflows", path: "/doing/workflows", owns: under("/doing/workflows"), load: loaders.workflows },
    { id: "skills", label: "Skills", path: "/doing/skills", owns: under("/doing/skills"), load: loaders.skills },
  ];
  return <InterimSections label="Doing sections" sections={sections} fallback={fallback} />;
}
