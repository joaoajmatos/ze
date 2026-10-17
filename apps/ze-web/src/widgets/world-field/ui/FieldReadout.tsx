import type { WsScreenRef } from "@myguyze/ze-client";
import { useRef } from "react";
import { chipLabelOf, concernStateWords, pct, postureOf, provenanceWords, relDay, type Concern } from "@/shared/lib";
import { ChatAboutChip, Meter } from "@/shared/ui";
import { deadlinePhrase } from "./../lib/labels";

interface Props {
  concern: Concern;
  now: Date;
  offline: boolean;
  /** Pin the item where the next drop lands. */
  pinOnDrop: boolean;
  onPinOnDrop: (pinned: boolean) => void;
  onUnpin: (overrideId: string) => void;
  onTransition: (loopId: string, kind: "close" | "drop") => void;
  busy: boolean;
  error: boolean;
  onClose: () => void;
  onChatAbout?: (ref: WsScreenRef, element?: Element | null) => void;
}

const CHAT_KINDS = new Set(["loop", "goal", "hypothesis", "reminder"]);

/** The selected mark in full: what Ze holds, how sure, and why it sits where it does in the order. */
export function FieldReadout({ concern: c, now, offline, pinOnDrop, onPinOnDrop, onUnpin, onTransition, busy, error, onClose, onChatAbout }: Props) {
  const root = useRef<HTMLDivElement>(null);
  const posture = postureOf(c);
  const tone = c.slipped ? "hot" : posture === "inferred" || posture === "suspected" ? "dotted" : "default";
  const source = c.sources.length ? c.sources.join(", ") : provenanceWords(c.provenance);
  const canClose = c.kind === "loop" && (c.state === "active" || c.state === "drifting");
  const evidenceAge = c.updatedAt ? relDay(c.updatedAt, now) : null;

  return (
    <div className="readout" ref={root} role="region" aria-label={`Readout: ${c.title}`} tabIndex={-1}>
      <div className="k" style={{ gridColumn: "1 / -1", display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
        <span className="lbl ink">{c.title}</span>
        <span style={{ display: "inline-flex", gap: 6 }}>
          {onChatAbout && CHAT_KINDS.has(c.kind) && (
            <ChatAboutChip
              label={c.title}
              onClick={() => onChatAbout({ kind: c.kind, id: c.id, label: c.title, as_of: c.updatedAt?.toISOString() } as WsScreenRef, root.current)}
            />
          )}
          <button type="button" className="ctl" onClick={onClose} aria-label="Close readout">
            Esc
          </button>
        </span>
      </div>

      {c.partial ? (
        <div className="k" style={{ gridColumn: "1 / -1" }}>
          <span className="lbl">Details</span>
          <span className="muted">Details unavailable.</span>
        </div>
      ) : (
        <>
          {c.state && (
            <div className="k">
              <span className="lbl">State</span>
              <span className={c.slipped ? "hot" : ""}>{concernStateWords(c)}</span>
            </div>
          )}
          {chipLabelOf(posture) && (
            <div className="k">
              <span className="lbl">Claim</span>
              <span>{chipLabelOf(posture)}</span>
            </div>
          )}
          {source && (
            <div className="k">
              <span className="lbl">Source</span>
              <span>{source}</span>
            </div>
          )}
          <div className="k">
            <span className="lbl">Sure</span>
            {c.confidence == null ? (
              <span className="muted">Not a claim</span>
            ) : (
              <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <Meter value={c.confidence} tone={tone} /> <span className="ro">{pct(c.confidence)}</span>
              </span>
            )}
          </div>
          {evidenceAge && (
            <div className="k">
              <span className="lbl">Last evidence</span>
              <span>{evidenceAge}</span>
            </div>
          )}
          <div className="k">
            <span className="lbl">{c.dueLabel === "reminder" ? "Reminder" : "Deadline"}</span>
            <span>{deadlinePhrase(c.due, now)}</span>
          </div>
          {c.progress && (
            <div className="k">
              <span className="lbl">Progress</span>
              <span>
                <span className="ro">{c.progress.done}/{c.progress.total}</span>
                {c.progress.next ? ` · next: ${c.progress.next}` : ""}
                {c.progress.stuckSince ? ` · stuck since ${relDay(new Date(c.progress.stuckSince), now)}` : ""}
              </span>
            </div>
          )}
          {c.driftRationale && (
            <div className="k" style={{ gridColumn: "1 / -1" }}>
              <span className="lbl hot">Why it slipped</span>
              <span>{c.driftRationale}</span>
            </div>
          )}
        </>
      )}

      {c.rank != null && (
        <div className="k" style={{ gridColumn: "1 / -1" }}>
          <span className="lbl">Why this order</span>
          <span>
            Shown <span className="ro">#{c.rank}</span>
            {c.computedRank != null && c.overridden ? (
              <>
                {" "}
                · Ze computed <span className="ro">#{c.computedRank}</span>; you moved it{c.pinned ? " and pinned it" : ""}.
              </>
            ) : (
              <> · where Ze computed it.</>
            )}
          </span>
          <span style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
            <label style={{ display: "inline-flex", gap: 6, alignItems: "center", minHeight: 44 }}>
              <input type="checkbox" checked={pinOnDrop} disabled={offline} onChange={(e) => onPinOnDrop(e.target.checked)} /> Pin where I drop it
            </label>
            {c.override && (
              <button type="button" className="ctl" disabled={offline || busy} onClick={() => onUnpin(c.override!.id)}>
                Unpin
              </button>
            )}
            <span className="s">Space lifts a mark, arrows move it, Space drops it.</span>
          </span>
        </div>
      )}

      {canClose && (
        <div className="k" style={{ gridColumn: "1 / -1", display: "flex", gap: 8 }}>
          <button type="button" className="ctl" disabled={offline || busy} onClick={() => onTransition(c.id, "close")}>
            Close it, it's done
          </button>
          <button type="button" className="ctl" disabled={offline || busy} onClick={() => onTransition(c.id, "drop")}>
            Drop
          </button>
        </div>
      )}
      {error && (
        <p className="hot" role="alert" style={{ gridColumn: "1 / -1", fontSize: "0.875rem" }}>
          That didn't go through. Try again.
        </p>
      )}
    </div>
  );
}
