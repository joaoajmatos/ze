import type { WsConfirmAction } from "@myguyze/ze-client";
import type { ReactNode } from "react";
import { useState } from "react";
import { cn } from "@/shared/lib/cn";

interface ConfirmBarProps {
  prompt: string;
  actions: WsConfirmAction[];
  onConfirm: (value: string, editedContent?: string) => void;
  editable?: boolean;
  proposed?: string;
  modeSwitcher?: ReactNode;
}

export function ConfirmBar({
  prompt,
  actions,
  onConfirm,
  editable = false,
  proposed = "",
  modeSwitcher,
}: ConfirmBarProps) {
  const [draft, setDraft] = useState(proposed);

  return (
    <div className="relative z-10 mb-3 w-full rounded-pill border border-plum-voltage/40 bg-plum-voltage/5 p-4">
      <p className="text-sm text-foreground mb-3">{prompt}</p>
      {modeSwitcher && <div className="mb-3">{modeSwitcher}</div>}
      {editable && (
        <textarea
          aria-label="Edit proposed workspace content"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="mb-3 w-full min-h-[5rem] rounded-xl border border-foreground/15 bg-background/30 p-3 text-xs font-mono text-foreground focus:outline-none focus:border-plum-voltage/50"
        />
      )}
      <div className="flex flex-wrap gap-2">
        {actions.map((action) => (
          <button
            key={`${action.label}-${action.value}`}
            onClick={() =>
              onConfirm(action.value, editable ? draft : undefined)
            }
            className={cn(
              "px-4 py-2 rounded-pill text-xs font-semibold tracking-wide transition-opacity",
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
