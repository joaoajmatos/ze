import { useEffect, useRef, type FormEvent } from "react";
import { useLocation } from "react-router-dom";
import { presenceActions, usePresenceStore } from "@/entities/presence";
import { useSendNotice } from "@/shared/lib";
import { Control } from "@/shared/ui";
import { useAskOverlay } from "../model/ask-overlay";
import { resolveScreenContext } from "../model/resolve-screen";

/** The sticky Ask input on every place except Ask. Submitting opens the contextual overlay. */
export function AskBar() {
  const { pathname, search } = useLocation();
  const offline = usePresenceStore((s) => s.presence.offline);
  const text = useAskOverlay((s) => s.draft);
  const setDraft = useAskOverlay((s) => s.setDraft);
  const focusTick = useAskOverlay((s) => s.focusTick);
  const submit = useAskOverlay((s) => s.submit);
  const field = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (focusTick > 0) field.current?.focus();
  }, [focusTick]);

  // The draft lives in the store, so presence follows it however it changed.
  useEffect(() => {
    presenceActions.askText(text.trim() !== "");
  }, [text]);

  useEffect(
    () => () => {
      presenceActions.askText(false);
      presenceActions.askBlur();
    },
    [],
  );

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || offline) return;
    if (!submit(trimmed, resolveScreenContext(pathname, search))) {
      useSendNotice.getState().showNotice("Ze has not sent your last message yet. Wait for it, then send this one.");
    }
  }

  const label = offline ? "Ask Ze — Ze is offline" : "Ask Ze";
  return (
    <form className="bottom" onSubmit={onSubmit}>
      <div className="ask">
        <input
          ref={field}
          data-ask-input=""
          value={text}
          disabled={offline}
          placeholder={offline ? "Ze is offline" : "Ask Ze"}
          aria-label={label}
          autoComplete="off"
          onChange={(e) => setDraft(e.target.value)}
          onFocus={presenceActions.askFocus}
          onBlur={presenceActions.askBlur}
        />
        <Control disabled aria-label="Voice input arrives later" title="Voice input arrives later">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.25" aria-hidden="true">
            <rect x="5.5" y="1.5" width="5" height="8" rx="2.5" />
            <path d="M3 7.5a5 5 0 0 0 10 0M8 12.5v2" />
          </svg>
        </Control>
        <Control type="submit" primary disabled={offline || text.trim() === ""} aria-label={offline ? "Ask — Ze is offline" : "Ask"}>
          Ask
        </Control>
      </div>
    </form>
  );
}
