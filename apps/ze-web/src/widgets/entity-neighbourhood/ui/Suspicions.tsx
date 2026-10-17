import type { WsScreenRef } from "@myguyze/ze-client";
import { useHypothesesQuery, useHypothesisFeedbackMutation } from "@/entities/hypothesis";
import { chipLabelOf, glyphOf, postureOf, stateWords } from "@/shared/lib/claim-posture";
import { ChatAboutChip, Chip, Control, Glyph, Module } from "@/shared/ui";

export function Suspicions({ entityId, onChatAbout }: { entityId: string; onChatAbout?: (ref: WsScreenRef, element: Element) => void }) {
  const { data } = useHypothesesQuery({ state: "all", entityId });
  const feedback = useHypothesisFeedbackMutation();
  const items = data ?? [];
  if (items.length === 0) return null;

  return (
    <Module label="I suspect…">
      <ul className="belief-list">
        {items.map((h) => {
          const posture = postureOf(h.claim_kind);
          const dismissed = h.feedback === "not_relevant" || h.feedback === "muted";
          return (
            <li key={h.id} className="row dotted">
              <span className="t">
                <Glyph kind={(glyphOf(posture) || "inferred") as "inferred" | "suspected"} />
                {h.summary}
              </span>
              <span className="ro">{h.confidence.toFixed(2)}</span>
              <span className="s">
                <Chip kind="dotted">{chipLabelOf(posture)}</Chip> {stateWords(h.relation)}
                {h.evidence.length > 0 && <> · from {h.evidence.map((e) => e.label).join(", ")}</>}
                {dismissed && <> · dismissed</>}
              </span>
              <span className="belief-actions">
                {dismissed ? (
                  <Control disabled={feedback.isPending} onClick={() => feedback.mutate({ hypothesisId: h.id, feedback: null })}>Clear</Control>
                ) : (
                  <>
                    <Control disabled={feedback.isPending} onClick={() => feedback.mutate({ hypothesisId: h.id, feedback: "useful" })}>Useful</Control>
                    <Control disabled={feedback.isPending} onClick={() => feedback.mutate({ hypothesisId: h.id, feedback: "not_relevant" })}>Not relevant</Control>
                    <Control disabled={feedback.isPending} onClick={() => feedback.mutate({ hypothesisId: h.id, feedback: "muted" })}>Mute</Control>
                  </>
                )}
                {onChatAbout && (
                  <ChatAboutChip
                    label="this suspicion"
                    onClick={(chip) =>
                      onChatAbout({ kind: "hypothesis", id: h.id, label: h.summary, component: "suspicion_row" }, chip.closest("li") ?? chip)
                    }
                  />
                )}
              </span>
            </li>
          );
        })}
      </ul>
    </Module>
  );
}
