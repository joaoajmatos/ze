import { ChoosePalette } from "@/features/choose-palette";
import { InterimSections, type InterimSection, type PageLoader } from "@/shared/ui";

type Loaders = { usage: PageLoader; data: PageLoader; settings: PageLoader };

/** Governance's interim content; phase 190 replaces this file. Usage is the index. */
export function GovernanceInterim({ loaders, fallback }: { loaders: Loaders; fallback?: React.ReactNode }) {
  const sections: readonly InterimSection[] = [
    { id: "usage", label: "Usage", path: "/governance", owns: (p) => p === "/governance", load: loaders.usage },
    { id: "data", label: "Data", path: "/governance/data", owns: (p) => p === "/governance/data", load: loaders.data },
    { id: "settings", label: "Settings", path: "/governance/settings", owns: (p) => p === "/governance/settings", load: loaders.settings },
  ];
  return (
    <InterimSections
      label="Governance sections"
      sections={sections}
      fallback={fallback}
      header={(id) => (id === "settings" ? <ChoosePalette /> : null)}
    />
  );
}
