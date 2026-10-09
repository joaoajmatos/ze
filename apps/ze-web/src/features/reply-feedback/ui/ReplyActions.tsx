import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  useSetMessageFeedbackMutation,
  type FeedbackRating,
  type MessageFeedback,
} from "@/entities/message-feedback";
import { cn } from "@/shared/lib";

interface ReplyActionsProps {
  messageId: string;
  feedback: MessageFeedback | undefined;
  /** Retry control, mounted by the widget so features stay independent. */
  retry?: ReactNode;
}

const ERROR_MS = 4000;

const thumbClass =
  "inline-flex h-11 w-11 items-center justify-center rounded-full text-smoke transition-colors hover:bg-foreground/[0.08] hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-plum-voltage aria-pressed:bg-plum-voltage/20 aria-pressed:text-plum-voltage";

export function ReplyActions({ messageId, feedback, retry }: ReplyActionsProps) {
  const mutation = useSetMessageFeedbackMutation();
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const current = feedback?.current ?? null;

  function press(target: "up" | "down") {
    if (!feedback) return;
    const rating: FeedbackRating = current === target ? "none" : target;
    setError(null);
    mutation.mutate(
      { messageId, rating, idempotencyKey: crypto.randomUUID() },
      {
        onError: () => {
          setError("Couldn't save your rating. Try again.");
          if (timer.current) clearTimeout(timer.current);
          timer.current = setTimeout(() => setError(null), ERROR_MS);
        },
      },
    );
  }

  return (
    <div
      data-testid="reply-actions"
      className={cn(
        "mt-1 flex flex-col items-start gap-1 transition-opacity",
        "opacity-0 group-hover/reply:opacity-100 group-focus-within/reply:opacity-100",
        "[@media(hover:none)]:opacity-100",
      )}
    >
      <div role="group" aria-label="Reply feedback" className="flex items-center gap-0.5">
        <button
          type="button"
          aria-label="Good reply"
          aria-pressed={current === "up"}
          disabled={!feedback}
          onClick={() => press("up")}
          className={thumbClass}
        >
          <ThumbsUp className="h-4 w-4" aria-hidden="true" />
        </button>
        <button
          type="button"
          aria-label="Bad reply"
          aria-pressed={current === "down"}
          disabled={!feedback}
          onClick={() => press("down")}
          className={thumbClass}
        >
          <ThumbsDown className="h-4 w-4" aria-hidden="true" />
        </button>
        {retry}
      </div>
      {error && (
        <p role="status" className="px-1 text-[10px] text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
