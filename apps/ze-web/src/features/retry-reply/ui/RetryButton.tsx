import { RotateCw } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import type { RetryEligibility } from "@/entities/message-feedback";
import { cn } from "@/shared/lib";

interface RetryButtonProps {
  eligibility: RetryEligibility | undefined;
  isLatest: boolean;
  connected: boolean;
  /** A turn or retry is running on this thread. */
  busy: boolean;
  retrying: boolean;
  /** Called with the entry ids the user agreed to undo; omitted for a text-only retry. */
  onRetry: (confirmedPlan?: string[]) => void;
}

const DISCONNECTED_TEXT = "Reconnecting. Retry needs a live connection.";
const BUSY_TEXT = "Ze is still working on a reply.";
const NOT_LATEST_TEXT = "Only the latest reply can be retried.";
const UNKNOWN_TEXT = "Ze cannot tell what this reply did.";

function reasonFor({
  eligibility,
  isLatest,
  connected,
  busy,
}: Pick<RetryButtonProps, "eligibility" | "isLatest" | "connected" | "busy">): string | null {
  if (!connected) return DISCONNECTED_TEXT;
  if (busy) return BUSY_TEXT;
  if (!isLatest) return eligibility?.reason_text ?? NOT_LATEST_TEXT;
  if (!eligibility?.available) return eligibility?.reason_text ?? UNKNOWN_TEXT;
  return null;
}

export function RetryButton(props: RetryButtonProps) {
  const { eligibility, retrying, onRetry } = props;
  const reasonId = useId();
  const titleId = useId();
  const [showReason, setShowReason] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const retryRef = useRef<HTMLButtonElement>(null);
  const continueRef = useRef<HTMLButtonElement>(null);
  const plan = eligibility?.plan ?? [];

  useEffect(() => {
    if (confirming) continueRef.current?.focus();
  }, [confirming]);

  function closeConfirm() {
    setConfirming(false);
    retryRef.current?.focus();
  }

  // A turn waiting on a confirmation has no reply to regenerate yet.
  if (!eligibility || eligibility.reason_code === "turn_pending") return null;

  const reason = reasonFor(props);
  const disabled = reason !== null;

  return (
    <div
      className="relative flex items-center"
      onMouseEnter={() => setShowReason(true)}
      onMouseLeave={() => setShowReason(false)}
    >
      <button
        ref={retryRef}
        type="button"
        aria-label="Retry reply"
        aria-expanded={plan.length > 0 && !disabled ? confirming : undefined}
        aria-disabled={disabled}
        aria-describedby={disabled ? reasonId : undefined}
        onFocus={() => setShowReason(true)}
        onBlur={() => setShowReason(false)}
        onClick={() => {
          if (disabled) {
            setShowReason(true);
            return;
          }
          if (plan.length > 0) {
            setConfirming(true);
            return;
          }
          onRetry();
        }}
        className={cn(
          "inline-flex h-11 w-11 items-center justify-center rounded-full text-smoke transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-plum-voltage",
          disabled
            ? "cursor-not-allowed opacity-50"
            : "hover:bg-foreground/[0.08] hover:text-foreground",
        )}
      >
        <RotateCw className={cn("h-4 w-4", retrying && "animate-spin")} aria-hidden="true" />
      </button>
      {confirming && !disabled && plan.length > 0 && (
        <div
          role="group"
          aria-labelledby={titleId}
          data-testid="retry-confirm"
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              e.stopPropagation();
              closeConfirm();
            }
          }}
          className="absolute left-0 top-full z-20 mt-1 w-72 rounded-lg border border-foreground/15 bg-background p-3 text-xs text-foreground shadow-lg"
        >
          <p id={titleId} className="font-medium">
            Retrying will undo what this reply did:
          </p>
          <ul className="mt-2 flex flex-col gap-1.5">
            {plan.map((entry) => (
              <li key={entry.entry_id}>
                <span>{entry.effect_phrase}</span>
                {entry.undo_note && (
                  <span className="block text-[10px] text-smoke">{entry.undo_note}</span>
                )}
              </li>
            ))}
          </ul>
          <div className="mt-3 flex justify-end gap-2">
            <button
              type="button"
              onClick={closeConfirm}
              className="rounded-pill px-3 py-1.5 text-smoke hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-plum-voltage"
            >
              Cancel
            </button>
            <button
              ref={continueRef}
              type="button"
              onClick={() => {
                setConfirming(false);
                onRetry(plan.map((entry) => entry.entry_id));
              }}
              className="rounded-pill bg-plum-voltage/20 px-3 py-1.5 text-plum-voltage focus-visible:outline focus-visible:outline-2 focus-visible:outline-plum-voltage"
            >
              Continue
            </button>
          </div>
        </div>
      )}
      {disabled && (
        <span
          id={reasonId}
          data-testid="retry-reason"
          className={
            showReason
              ? "ml-1 max-w-[16rem] text-[10px] leading-snug text-smoke"
              : "sr-only"
          }
        >
          {reason}
        </span>
      )}
    </div>
  );
}
