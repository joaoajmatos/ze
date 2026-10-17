import { useEffect } from "react";
import { CommandChip } from "@/shared/ui";
import { useAskOverlay } from "../model/ask-overlay";

interface AboutPanelProps {
  /** Selector of the input that owns the keyboard: keys 1-3 pick a suggestion while it is empty and focused. */
  inputSelector: string;
  onPick: (text: string) => void;
}

/** The subject chip (removable) and three suggestions for a "Chat about this" chat. */
export function AboutPanel({ inputSelector, onPick }: AboutPanelProps) {
  const about = useAskOverlay((s) => s.about);
  const clearAbout = useAskOverlay((s) => s.clearAbout);

  useEffect(() => {
    if (!about) return;
    const onKey = (e: KeyboardEvent) => {
      const index = ["1", "2", "3"].indexOf(e.key);
      if (index < 0 || e.metaKey || e.ctrlKey || e.altKey) return;
      const field = document.querySelector<HTMLInputElement | HTMLTextAreaElement>(inputSelector);
      if (!field || document.activeElement !== field || field.value !== "") return;
      const text = about.suggestions[index];
      if (!text) return;
      e.preventDefault();
      onPick(text);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [about, inputSelector, onPick]);

  if (!about) return null;
  const label = about.ref.label ?? about.ref.id;
  return (
    <div className="about-panel" role="group" aria-label="Chat about">
      <span className="chip">
        <span className="lbl">About</span> {label}
        <button type="button" className="about-remove" aria-label={`Stop chatting about ${label}`} onClick={clearAbout}>
          ✕
        </button>
      </span>
      <ol className="about-suggestions">
        {about.suggestions.map((text, i) => (
          <li key={text}>
            <CommandChip index={String(i + 1)} keyHint={String(i + 1)} aria-keyshortcuts={String(i + 1)} onClick={() => onPick(text)}>
              {text}
            </CommandChip>
          </li>
        ))}
      </ol>
    </div>
  );
}
