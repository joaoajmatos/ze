import { useEffect } from "react";

const TEXT_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

/** `/` focuses the Ask input (the bar, or the composer on Ask) unless the user is already typing. */
export function useAskShortcut(): void {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target instanceof HTMLElement ? e.target : null;
      if (target && (TEXT_TAGS.has(target.tagName) || target.isContentEditable)) return;
      const field = document.querySelector<HTMLElement>("[data-ask-input]");
      if (!field) return;
      e.preventDefault();
      field.focus();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
