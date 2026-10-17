import type { WsConfirmAction } from "@myguyze/ze-client";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/shared/lib/cn";
import { CommandChip, Control, Module } from "@/shared/ui";
import type { ConfirmItem, ConfirmSource } from "../model/types";

interface ConfirmationCardProps {
  title: string;
  items: ConfirmItem[];
  actions: WsConfirmAction[];
  onRespond: (value: string, edits: Record<string, string>) => void;
  source?: ConfirmSource | null;
  disabled?: boolean;
  highlighted?: boolean;
}

export function ConfirmationCard({
  title,
  items,
  actions,
  onRespond,
  source = null,
  disabled = false,
  highlighted = false,
}: ConfirmationCardProps) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (highlighted) rootRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [highlighted]);

  function editsFor(value: string): Record<string, string> {
    if (value !== "approve") return {};
    const edits: Record<string, string> = {};
    for (const item of items) {
      const draft = drafts[item.item_id];
      if (item.editable_field && draft !== undefined && draft !== (item.proposed_text ?? "")) {
        edits[item.item_id] = draft;
      }
    }
    return edits;
  }

  const prompt = items.length === 0;
  return (
    <div ref={rootRef} className={cn("confirm-card", highlighted && "is-highlighted")}>
      <Module label={title} tone="cream" as="div">
        {source && (
          <p data-testid="confirm-source" className="ro">
            From {source.kind}: {source.name}
          </p>
        )}
        {items.length > 0 && (
          <ul className="confirm-items">
            {items.map((item) => (
              <li key={item.item_id}>
                <p className="key">{item.effect_phrase}</p>
                <p className="muted">{item.summary}</p>
                {item.conflict && (
                  <p data-testid="confirm-conflict" role="note" className="lbl hot">
                    {item.conflict}
                  </p>
                )}
                {item.editable_field && (
                  <textarea
                    aria-label={`Edit ${item.editable_field}`}
                    value={drafts[item.item_id] ?? item.proposed_text ?? ""}
                    disabled={disabled}
                    onChange={(e) => setDrafts((d) => ({ ...d, [item.item_id]: e.target.value }))}
                    className="confirm-edit"
                  />
                )}
              </li>
            ))}
          </ul>
        )}
        <div className="confirm-actions">
          {actions.map((action) =>
            prompt ? (
              <CommandChip
                key={`${action.label}-${action.value}`}
                index="→"
                disabled={disabled}
                onClick={() => onRespond(action.value, {})}
              >
                {action.label}
              </CommandChip>
            ) : (
              <Control
                key={`${action.label}-${action.value}`}
                primary={action.style === "primary" || !action.style}
                disabled={disabled}
                onClick={() => onRespond(action.value, editsFor(action.value))}
              >
                {action.label}
              </Control>
            ),
          )}
        </div>
      </Module>
    </div>
  );
}
