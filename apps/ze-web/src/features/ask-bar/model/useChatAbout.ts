import type { WsScreenRef } from "@myguyze/ze-client";
import { useCallback } from "react";
import { placeOf } from "@/shared/config";
import { useAskOverlay } from "./ask-overlay";
import { suggestionsFor } from "./suggestions";

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * "Chat about this": start a chat with `ref` as the subject. Off Ask the contextual overlay opens
 * with the subject, three suggestions and an empty focused bar; on Ask the composer takes the subject
 * chip and the suggestions. Either way the orb glances at `element` (skipped under reduced motion).
 */
export function useChatAbout(): (ref: WsScreenRef, element?: Element | null) => void {
  return useCallback((ref, element) => {
    // Read at click time, so the hook needs no router and a page that changed meanwhile is respected.
    const onAsk = placeOf(window.location.pathname)?.id === "ask";
      useAskOverlay.getState().startAbout(
        { ref, origin: "chat_about", suggestions: suggestionsFor(ref.kind) },
        { inPlace: onAsk, element, glance: !prefersReducedMotion() },
      );
  }, []);
}
