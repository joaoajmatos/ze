import type { WsConfirmAction } from "@myguyze/ze-client";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/shared/lib/cn";
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

  return (
    <div
      ref={rootRef}
      className={cn(
        "relative z-10 mb-3 w-full rounded-pill border border-plum-voltage/40 bg-plum-voltage/5 p-4",
        highlighted && "ring-2 ring-plum-voltage/60",
      )}
    >
      <p className="text-sm font-medium text-foreground">{title}</p>
      {source && (
        <p data-testid="confirm-source" className="mt-1 text-xs text-smoke">
          From {source.kind}: {source.name}
        </p>
      )}
      {items.length > 0 && (
        <ul className="my-3 space-y-3">
          {items.map((item) => (
            <li key={item.item_id} className="text-sm text-foreground">
              <p className="font-medium">{item.effect_phrase}</p>
              <p className="text-xs text-smoke">{item.summary}</p>
              {item.conflict && (
                <p
                  data-testid="confirm-conflict"
                  role="note"
                  className="mt-1 inline-block rounded bg-destructive/10 px-2 py-0.5 text-xs text-destructive"
                >
                  {item.conflict}
                </p>
              )}
              {item.editable_field && (
                <textarea
                  aria-label={`Edit ${item.editable_field}`}
                  value={drafts[item.item_id] ?? item.proposed_text ?? ""}
                  disabled={disabled}
                  onChange={(e) => setDrafts((d) => ({ ...d, [item.item_id]: e.target.value }))}
                  className="mt-2 w-full min-h-[5rem] rounded-xl border border-foreground/15 bg-background/30 p-3 text-xs font-mono text-foreground focus:outline-none focus:border-plum-voltage/50 disabled:opacity-60"
                />
              )}
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-2">
        {actions.map((action) => (
          <button
            key={`${action.label}-${action.value}`}
            type="button"
            disabled={disabled}
            onClick={() => onRespond(action.value, editsFor(action.value))}
            className={cn(
              "px-4 py-2 rounded-pill text-xs font-semibold tracking-wide transition-opacity disabled:opacity-50",
              action.style === "primary" || !action.style
                ? "bg-plum-voltage text-foreground"
                : action.style === "danger"
                  ? "border border-destructive text-destructive"
                  : "border border-foreground/20 text-foreground",
            )}
          >
            {action.label}
          </button>
        ))}
      </div>
    </div>
  );
}
