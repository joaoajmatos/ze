import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@/app/styles/globals.css";
import { App } from "@/app/App";
import { applyConfig, applyPalette, readPalette } from "@/shared/lib";

applyConfig();
applyPalette(readPalette());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
