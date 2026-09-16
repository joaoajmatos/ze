import type { ReactNode } from "react";
import type { LearningResponse } from "@myguyze/ze-client";

interface GoalLearningsListProps {
  learnings: LearningResponse[];
  reviewSlot?: (learning: LearningResponse) => ReactNode;
}

function claimLabel(kind: string): string {
  if (kind === "inference") return "INFERENCE (tentative)";
  if (kind === "fact") return "FACT";
  return kind.toUpperCase();
}

export function GoalLearningsList({ learnings, reviewSlot }: GoalLearningsListProps) {
  if (!learnings.length) {
    return <p className="text-xs text-smoke/80 italic">No learnings yet.</p>;
  }

  return (
    <ul className="space-y-3">
      {learnings.map((learning) => (
        <li key={learning.id} className="flex flex-col gap-1 text-xs text-smoke">
          <div className="flex items-start gap-2">
            <span className="mt-0.5 text-plum-voltage flex-shrink-0">•</span>
            <span>
              <span className="mr-2 uppercase tracking-wide text-[10px] text-smoke/70">
                {claimLabel(learning.claim_kind)}
              </span>
              {learning.content}
            </span>
          </div>
          <span className="pl-4 text-[10px] text-smoke/60">
            {learning.status}
            {learning.evidence_count ? ` · ${learning.evidence_count} evidence` : ""}
          </span>
          {reviewSlot?.(learning)}
        </li>
      ))}
    </ul>
  );
}
