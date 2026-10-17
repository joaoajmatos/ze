import { useEffect } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { SectionTabs } from "@/shared/ui";
import { JarvisShell } from "./JarvisShell";
import { AssembleView } from "./views/AssembleView";
import { WorldView } from "./views/WorldView";

const VIEWS = [
  { id: "world", label: "World", path: "/jarvis" },
  { id: "assemble", label: "Assemble", path: "/jarvis/assemble" },
];

/** The design reference, rendered inside the real shell until phase 193 deletes it. */
export function JarvisApp() {
  const { pathname } = useLocation();
  const assemble = pathname.endsWith("/assemble");
  useEffect(() => {
    document.title = assemble ? "Ze · Assemble" : "Ze · World";
  }, [assemble]);
  return (
    <JarvisShell>
      <SectionTabs label="Reference views" sections={VIEWS} currentId={assemble ? "assemble" : "world"} />
      <Routes>
        <Route index element={<WorldView />} />
        <Route path="assemble" element={<AssembleView />} />
      </Routes>
    </JarvisShell>
  );
}
