import { SectionPanel } from "@/shared/ui";
import { useProcedureCandidatesQuery } from "@/entities/procedure";
import { ReviewProcedureCandidate } from "@/features/review-procedure";

export function ProcedureCandidatesList() {
  const { data, isLoading } = useProcedureCandidatesQuery();
  const candidates = data ?? [];

  if (isLoading || candidates.length === 0) {
    return null;
  }

  return (
    <SectionPanel>
      <h2 className="text-sm font-medium text-foreground mb-4">Procedure candidates</h2>
      <ul className="space-y-4">
        {candidates.map((candidate) => (
          <li key={candidate.id} className="space-y-2">
            <p className="text-sm text-foreground">{candidate.name}</p>
            <p className="text-xs text-smoke">
              {candidate.source_kind} · {candidate.status} · {candidate.evidence_refs.length}{" "}
              evidence
            </p>
            <ReviewProcedureCandidate candidate={candidate} />
          </li>
        ))}
      </ul>
    </SectionPanel>
  );
}
