import type { WsScreenContext } from "@myguyze/ze-client";
import { Paperclip, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { presenceActions, usePresenceStore } from "@/entities/presence";
import { placeWorkspaceFile } from "@/entities/workspace";
import { useSendNotice } from "@/shared/lib";
import { Control } from "@/shared/ui";
import { useAskOverlay } from "../model/ask-overlay";

interface Attachment {
  path: string;
  size: number;
  name: string;
}

interface AskBarProps {
  /** Sends the message. `explicitContext` is what a chat-about (or `askAbout`) chose; false means not accepted. */
  onSubmit: (text: string, explicitContext: WsScreenContext | null, workspacePlaced: { path: string; size: number }[] | undefined) => boolean;
  /** Why the bar cannot be used right now (another window has the connection). */
  disabledReason?: string | null;
  /** The mic button, one cell of the bar. `blocked` is the bar's own reason when it cannot be used. */
  renderMic?: (blocked: string | null) => ReactNode;
  /** The voice status line, above the bar like the attachment chips so the bar never changes height. */
  renderVoiceStatus?: () => ReactNode;
}

/** The sticky Ask input on every place. Where the message goes is the caller's business. */
export function AskBar({ onSubmit, disabledReason = null, renderMic, renderVoiceStatus }: AskBarProps) {
  const offline = usePresenceStore((s) => s.presence.offline);
  const text = useAskOverlay((s) => s.draft);
  const setDraft = useAskOverlay((s) => s.setDraft);
  const focusTick = useAskOverlay((s) => s.focusTick);
  const field = useRef<HTMLInputElement>(null);
  const files = useRef<HTMLInputElement>(null);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [attaching, setAttaching] = useState(false);
  const blocked = disabledReason ?? (offline ? "Ze is offline" : null);

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

  async function attach(file: File) {
    setAttaching(true);
    try {
      const placed = await placeWorkspaceFile(file);
      setAttachments((prev) => [...prev, { path: placed.path, size: placed.size, name: file.name }]);
    } catch {
      useSendNotice.getState().showNotice("Could not place the file in the workspace.");
    } finally {
      setAttaching(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || blocked) return;
    const placed = attachments.length ? attachments.map(({ path, size }) => ({ path, size })) : undefined;
    const { explicitContext, voiceId } = useAskOverlay.getState();
    const explicit = voiceId ? { ...(explicitContext ?? {}), voice: { transcription_id: voiceId } } : explicitContext;
    if (!onSubmit(trimmed, explicit, placed)) {
      useSendNotice.getState().showNotice("Ze has not sent your last message yet. Wait for it, then send this one.");
      return;
    }
    setAttachments([]);
    setDraft("");
    useAskOverlay.getState().aboutSent();
  }

  const label = blocked ? `Ask Ze — ${blocked}` : "Ask Ze";
  return (
    <form className="bottom" onSubmit={submit}>
      {renderVoiceStatus?.()}
      {attachments.length > 0 && (
        <div className="chips ask-attachments">
          {attachments.map((item) => (
            <span key={item.path} className="chip solid">
              {item.name}
              <button type="button" className="ctl-text" aria-label={`Remove ${item.name}`} onClick={() => setAttachments((prev) => prev.filter((a) => a.path !== item.path))}>
                <X size={10} aria-hidden="true" />
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="ask">
        <input ref={files} type="file" hidden aria-label="Attach file to workspace input" onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) void attach(file);
        }} />
        <Control disabled={Boolean(blocked) || attaching} aria-label="Attach file to workspace" title="Attach file to workspace" onClick={() => files.current?.click()}>
          <Paperclip size={16} aria-hidden="true" />
        </Control>
        <input
          ref={field}
          data-ask-input=""
          value={text}
          disabled={Boolean(blocked)}
          placeholder={blocked ?? "Ask Ze"}
          aria-label={label}
          autoComplete="off"
          onChange={(e) => setDraft(e.target.value)}
          onFocus={presenceActions.askFocus}
          onBlur={presenceActions.askBlur}
        />
        {renderMic?.(blocked)}
        <Control type="submit" primary disabled={Boolean(blocked) || attaching || text.trim() === ""} aria-label={blocked ? `Ask — ${blocked}` : "Ask"}>
          Ask
        </Control>
      </div>
    </form>
  );
}
