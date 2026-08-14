import type { WsConfirmAction } from "@myguyze/ze-client";
import { useState } from "react";
import { cn } from "@/shared/lib/cn";

interface ConfirmBarProps {
  prompt: string;
  actions: WsConfirmAction[];
  onConfirm: (value: string, editedContent?: string) => void;
  editable?: boolean;
  proposed?: string;
}

export function ConfirmBar({
  prompt,
  actions,
  onConfirm,
  editable = false,
  proposed = "",
}: ConfirmBarProps) {
  const [draft, setDraft] = useState(proposed);

  return (
    <div className="relative z-10 mb-3 w-full rounded-pill border border-plum-voltage/40 bg-plum-voltage/5 p-4">
      <p className="text-sm text-white mb-3">{prompt}</p>
      {editable && (
        <textarea
          aria-label="Edit proposed workspace content"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="mb-3 w-full min-h-[5rem] rounded-xl border border-white/15 bg-black/30 p-3 text-xs font-mono text-white focus:outline-none focus:border-plum-voltage/50"
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
                ? "bg-plum-voltage text-white"
                : action.style === "danger"
                  ? "border border-destructive text-destructive"
                  : "border border-white/20 text-white",
            )}
          >
            {action.label}
          </button>
        ))}
      </div>
    </div>
  );
}
