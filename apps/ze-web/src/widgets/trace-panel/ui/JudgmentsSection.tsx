import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { TraceSection } from "@/widgets/message-trace/ui/TraceSection";

type Judgment = NonNullable<WsTraceUpdateFrame["judgments"]>[number];

function judgmentsOf(trace: WsTraceUpdateFrame): Judgment[] {
  return trace.judgments ?? [];
}

interface JudgmentsSectionProps {
  trace: WsTraceUpdateFrame;
  live?: boolean;
}

function formatAnswer(item: Judgment): string {
  if (item.skip_reason) {
    return `skipped (${item.skip_reason})`;
  }
  if (item.answer == null) {
    return "—";
  }
  return String(item.answer);
}

export function JudgmentsSection({ trace, live }: JudgmentsSectionProps) {
  const judgments = judgmentsOf(trace);
  if (judgments.length === 0) {
    return null;
  }
  return (
    <TraceSection title="Judgments" count={judgments.length} loading={live}>
      <ul className="space-y-1.5">
        {judgments.map((item, i) => (
          <li
            key={`${item.question_id}-${i}`}
            className="flex items-center gap-2 text-xs flex-wrap"
          >
            <span className="font-mono text-foreground/90">{item.question_id}</span>
            <span className="px-1.5 py-0.5 rounded bg-foreground/[0.06] text-smoke text-[10px]">
              {item.kind}
            </span>
            <span className="text-foreground/90">{formatAnswer(item)}</span>
            {item.consumed ? (
              <span className="px-1.5 py-0.5 rounded bg-plum-voltage/20 text-plum-voltage text-[10px]">
                consumed
              </span>
            ) : (
              <span className="px-1.5 py-0.5 rounded bg-foreground/[0.06] text-smoke text-[10px]">
                unused
              </span>
            )}
            {item.model ? (
              <span className="font-mono text-[10px] text-smoke/80">{item.model}</span>
            ) : null}
          </li>
        ))}
      </ul>
    </TraceSection>
  );
}
