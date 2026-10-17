import { useEffect } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import "./jarvis.css";
import { JarvisShell } from "./JarvisShell";
import { AssembleView } from "./views/AssembleView";
import { WorldView } from "./views/WorldView";

export function JarvisApp() {
  const { pathname } = useLocation();
  const assemble = pathname.endsWith("/assemble");
  useEffect(() => {
    document.title = assemble ? "Ze · Assemble" : "Ze · World";
  }, [assemble]);
  return (
    <JarvisShell showAsk={!assemble}>
      <Routes>
        <Route index element={<WorldView />} />
        <Route path="assemble" element={<AssembleView />} />
      </Routes>
    </JarvisShell>
  );
}
