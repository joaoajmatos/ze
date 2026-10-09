import { RotateCw } from "lucide-react";
import { useId, useState } from "react";
import type { RetryEligibility } from "@/entities/message-feedback";
import { cn } from "@/shared/lib";

interface RetryButtonProps {
  eligibility: RetryEligibility | undefined;
  isLatest: boolean;
  connected: boolean;
  /** A turn or retry is running on this thread. */
  busy: boolean;
  retrying: boolean;
  onRetry: () => void;
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
  const [showReason, setShowReason] = useState(false);

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
        type="button"
        aria-label="Retry reply"
        aria-disabled={disabled}
        aria-describedby={disabled ? reasonId : undefined}
        onFocus={() => setShowReason(true)}
        onBlur={() => setShowReason(false)}
        onClick={() => {
          if (disabled) {
            setShowReason(true);
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
