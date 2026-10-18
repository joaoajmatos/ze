import { useEffect } from "react";
import { Route, Routes } from "react-router-dom";
import { JarvisShell } from "./JarvisShell";
import { WorldView } from "./views/WorldView";

/** The design reference, rendered inside the real shell until phase 193 deletes it. */
export function JarvisApp() {
  useEffect(() => {
    document.title = "Ze · World";
  }, []);
  return (
    <JarvisShell>
      <Routes>
        <Route index element={<WorldView />} />
      </Routes>
    </JarvisShell>
  );
}
