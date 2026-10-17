import type { LoopListItem, WsScreenRef } from "@myguyze/ze-client";
import { useScreenPublisher } from "@/entities/screen-context";
import { agoPhrase, concernGlyph, concernPosture, concernStateWords, provenanceWords } from "@/shared/lib";
import { ChatAboutChip, Glyph, Module, Spark } from "@/shared/ui";

interface Props {
  loops: LoopListItem[];
  loading: boolean;
  error: boolean;
  now: Date;
  offline: boolean;
  /** Key (`loop:<id>`) of the mark selected in the field. */
  selected: string | null;
  onSelect: (key: string) => void;
  onTransition: (loopId: string, kind: "close" | "drop") => void;
  busyId: string | null;
  onChatAbout?: (ref: WsScreenRef, element?: Element | null) => void;
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** Open loops, each with the same posture vocabulary as the field. Suspected ones wait in Needs you. */
export function LoopsRail({ loops, loading, error, now, offline, selected, onSelect, onTransition, busyId, onChatAbout }: Props) {
  const open = loops.filter((l) => l.state === "active" || l.state === "drifting");
  const suspected = loops.filter((l) => l.state === "suspected").length;

  useScreenPublisher({
    visible: open.slice(0, 10).map((l) => ({ kind: "loop", id: l.id }) as WsScreenRef),
  });

  return (
    <Module label="Loops · confidence" className="world-loops">
      {error ? (
        <p className="hot" role="alert">
          Couldn't read your loops.
        </p>
      ) : loading ? (
        <p className="muted">Reading…</p>
      ) : (
        <>
          {open.length === 0 && <p className="muted">No open loops.</p>}
          {open.map((l) => {
            const hot = l.state === "drifting";
            const posture = concernPosture({ kind: "loop", state: l.state, claimKind: l.claim_kind, provenance: l.provenance, confirmed: false, partial: false });
            const glyph = concernGlyph(posture) ?? "told";
            const prior = l.confidence_prior;
            const delta = prior != null ? l.confidence - prior : 0;
            const moved = prior != null && Math.abs(delta) >= 0.02;
            const source = l.source_inflows[0] ?? provenanceWords(l.provenance);
            const when = agoPhrase(l.updated_at ? new Date(l.updated_at) : null, now);
            return (
              <div key={l.id} className={`row loop ${hot ? "hot" : ""} ${l.state} ${selected === `loop:${l.id}` ? "focused" : ""}`}>
                <i className="tick" aria-hidden="true" />
                <button type="button" className="t ctl-text" onClick={() => onSelect(`loop:${l.id}`)} aria-pressed={selected === `loop:${l.id}`}>
                  <Glyph kind={glyph} hot={hot} /> {l.title.split(":")[0].trim()}
                </button>
                <span className="ro-stack">
                  {prior != null && <Spark from={prior} to={l.confidence} hot={hot} dotted={glyph !== "told"} label={`${Math.round(l.confidence * 100)}% sure${moved ? `, was ${Math.round(prior * 100)}%` : ""}`} />}
                  <span className={`ro ${hot ? "hot" : ""}`}>
                    {l.confidence.toFixed(2)}
                    {moved && <span className="delta">{delta < 0 ? "▾" : "▴"}{Math.abs(delta).toFixed(2)}</span>}
                  </span>
                </span>
                <span className="s">
                  {cap(concernStateWords({ kind: "loop", state: l.state, slipped: hot }))} · {source} · {when}
                </span>
                <span className="acts">
                  <button type="button" className="ctl" disabled={offline || busyId === l.id} onClick={() => onTransition(l.id, "close")}>
                    Close
                  </button>
                  <button type="button" className="ctl" disabled={offline || busyId === l.id} onClick={() => onTransition(l.id, "drop")}>
                    Drop
                  </button>
                  {onChatAbout && <ChatAboutChip label={l.title} onClick={() => onChatAbout({ kind: "loop", id: l.id, label: l.title } as WsScreenRef, null)} />}
                </span>
              </div>
            );
          })}
          {suspected > 0 && (
            <div className="row dotted">
              <span className="t">{suspected} suspected</span>
              <span className="lbl">in Needs you</span>
            </div>
          )}
        </>
      )}
    </Module>
  );
}
