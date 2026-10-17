import type { MemoryFeedItem } from "@myguyze/ze-client";
import { useRef, useState } from "react";
import { chipLabelOf, glyphOf, postureOf } from "@/shared/lib/claim-posture";
import { ChatAboutChip, Chip, Control, Glyph } from "@/shared/ui";
import { beliefSentence, sinceLabel, sourceWords } from "../lib/belief";

interface BeliefRowProps {
  item: MemoryFeedItem;
  onKeep: () => void;
  onDrop: () => void;
  onEdit: (value: string) => void;
  busy?: boolean;
  now?: Date;
  /** The row is part of the selection Ze can see on screen. */
  selected?: boolean;
  onToggleSelect?: () => void;
  onChatAbout?: (element: Element) => void;
}

export function BeliefRow({ item, onKeep, onDrop, onEdit, busy = false, now, selected = false, onToggleSelect, onChatAbout }: BeliefRowProps) {
  const root = useRef<HTMLLIElement>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(item.value ?? "");
  const posture = postureOf(item.claim_kind);
  const glyph = glyphOf(posture);
  const sentence = beliefSentence(item.key, item.value);
  const dotted = posture === "inferred" || posture === "suspected";

  function cancel() {
    setDraft(item.value ?? "");
    setEditing(false);
  }

  function save() {
    onEdit(draft.trim());
    setEditing(false);
  }

  return (
    <li ref={root} className={`row belief ${dotted ? "dotted" : ""} ${selected ? "selected" : ""}`}>
      <span className="t">
        <Glyph kind={(glyph || "told") as "told" | "inferred" | "suspected" | "goal"} />
        {onToggleSelect ? (
          <button type="button" className="ctl-text belief-select" aria-pressed={selected} onClick={onToggleSelect}>
            <span className={item.contradicted ? "struck" : undefined}>{sentence}</span>
          </button>
        ) : (
          <span className={item.contradicted ? "struck" : undefined}>{sentence}</span>
        )}
      </span>
      {item.confidence != null && <span className="ro">{item.confidence.toFixed(2)}</span>}
      <span className="s">
        <Chip kind={dotted ? "dotted" : "solid"}>{chipLabelOf(posture)}</Chip>
        {item.reviewed && <Chip>kept</Chip>}
        {item.contradicted && <Chip kind="dotted">contradicted</Chip>}{" "}
        {[sourceWords(item.provenance, item.agent), item.created_at ? sinceLabel(item.created_at, now) : ""].filter(Boolean).join(" · ")}
      </span>
      {editing ? (
        <span className="belief-actions">
          <input
            className="text-field"
            aria-label="New value"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") save();
              if (e.key === "Escape") cancel();
            }}
            autoFocus
          />
          <Control disabled={busy || !draft.trim()} onClick={save} aria-label="Save the new value">Save</Control>
          <Control onClick={cancel} aria-label="Cancel the edit">Cancel</Control>
        </span>
      ) : (
        <span className="belief-actions">
          <Control disabled={busy} onClick={onKeep} aria-label="Keep this belief">Keep</Control>
          <Control disabled={busy} onClick={() => setEditing(true)} aria-label="Edit this belief">Edit</Control>
          <Control disabled={busy} onClick={onDrop} aria-label="Drop this belief">Drop</Control>
          {onChatAbout && <ChatAboutChip label="this belief" onClick={() => root.current && onChatAbout(root.current)} />}
        </span>
      )}
    </li>
  );
}
