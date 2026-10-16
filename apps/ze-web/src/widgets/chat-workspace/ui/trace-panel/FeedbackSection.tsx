import type { MessageFeedback } from "@/entities/message-feedback";
import { TraceSection } from "@/entities/message-trace";
import { useSession } from "@/entities/session";
import { feedbackKindLabel, formatFeedbackTime } from "./lib/format";

interface FeedbackSectionProps {
  feedback: MessageFeedback | undefined;
  live?: boolean;
}

export function FeedbackSection({ feedback, live }: FeedbackSectionProps) {
  const setHighlightMessage = useSession((s) => s.setHighlightMessage);
  if (live || !feedback) return null;

  const { current, replaced_by, replaces, trace_present } = feedback;
  const history = feedback.history ?? [];
  const empty = !current && history.length === 0 && !replaced_by && !replaces;

  return (
    <TraceSection title="Feedback">
      <div className="space-y-1.5 text-xs">
        {empty ? (
          <p className="text-smoke">No feedback yet</p>
        ) : (
          <p className="text-foreground/90">
            Current rating:{" "}
            <span data-testid="feedback-current">
              {current === "up" ? "Thumbs up" : current === "down" ? "Thumbs down" : "None"}
            </span>
          </p>
        )}
        {history.length > 0 && (
          <ul aria-label="Feedback history" className="space-y-1">
            {history.map((item, i) => (
              <li key={`${item.kind}-${item.occurred_at}-${i}`} className="flex gap-2">
                <span className="text-foreground/90">{feedbackKindLabel(item.kind)}</span>
                <time dateTime={item.occurred_at} className="text-smoke/80">
                  {formatFeedbackTime(item.occurred_at)}
                </time>
              </li>
            ))}
          </ul>
        )}
        {replaced_by && (
          <p className="text-foreground/90">
            Retried ·{" "}
            <button
              type="button"
              onClick={() => setHighlightMessage(replaced_by)}
              className="text-plum-voltage underline underline-offset-2"
            >
              View replacement
            </button>
          </p>
        )}
        {replaces && <p className="text-foreground/90">Replaces an earlier reply</p>}
        {!trace_present && <p className="text-smoke">No trace recorded</p>}
      </div>
    </TraceSection>
  );
}
