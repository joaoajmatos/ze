import { useEffect } from "react";
import { useVoiceInput } from "./store";

const MIN_HOLD_MS = 300;

function inTextField(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT";
}

/** Hold `v` to talk, outside text fields. A hold under 300 ms is discarded. */
export function useHoldToTalk(enabled: boolean): void {
  useEffect(() => {
    if (!enabled) return;
    let heldSince: number | null = null;

    const release = () => {
      if (heldSince === null) return;
      const held = performance.now() - heldSince;
      heldSince = null;
      const { stop, dismiss } = useVoiceInput.getState();
      if (held < MIN_HOLD_MS) dismiss();
      else stop();
    };

    const down = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== "v" || e.repeat || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return;
      if (inTextField(e.target) || document.querySelector('[role="dialog"], dialog[open]')) return;
      if (useVoiceInput.getState().status !== "idle") return;
      heldSince = performance.now();
      useVoiceInput.getState().start();
    };
    const up = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "v") release();
    };

    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", release);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", release);
      // Turned off mid-hold (a displaced window): the recording was never finished, so drop it.
      if (heldSince !== null) {
        heldSince = null;
        useVoiceInput.getState().dismiss();
      }
    };
  }, [enabled]);
}
