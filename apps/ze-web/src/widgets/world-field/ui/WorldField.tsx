import type { PriorityOverrideRequestSchema, WsScreenRef } from "@myguyze/ze-client";
import { useState } from "react";
import { useLoopTransitionMutation } from "@/entities/loop";
import { useReprioritizeMutation, useUnpinPriorityOverrideMutation } from "@/entities/priority-item";
import { useScreenPublisher } from "@/entities/screen-context";
import type { Concern } from "@/shared/lib";
import { useReorder, type Move } from "../lib/useReorder";
import { FieldChart } from "./FieldChart";
import { FieldList } from "./FieldList";
import { FieldReadout } from "./FieldReadout";

interface Props {
  concerns: Concern[];
  now: Date;
  loading: boolean;
  error: boolean;
  narrow: boolean;
  offline: boolean;
  selected: string | null;
  onSelect: (key: string | null) => void;
  onChatAbout?: (ref: WsScreenRef, element?: Element | null) => void;
}

type RankedKind = PriorityOverrideRequestSchema["source_kind"];

/** The hero: the field (desktop) or the ranked list (phone), its legend, and the selected item's readout. */
export function WorldField({ concerns, now, loading, error, narrow, offline, selected, onSelect, onChatAbout }: Props) {
  const reprioritize = useReprioritizeMutation();
  const unpin = useUnpinPriorityOverrideMutation();
  const transition = useLoopTransitionMutation();
  const [pinOnDrop, setPinOnDrop] = useState(false);

  const reorder = useReorder(concerns, (m: Move) => {
    if (offline) return;
    reprioritize.mutate({
      source_kind: m.item.kind as RankedKind,
      source_id: m.item.id,
      anchor_source_kind: m.anchor.kind as RankedKind,
      anchor_source_id: m.anchor.id,
      relation: m.relation,
      pinned: pinOnDrop,
    });
  });

  const sel = concerns.find((c) => c.key === selected) ?? null;
  const shown = loading ? [] : concerns;

  useScreenPublisher({
    focused_module: "world-field",
    ...(sel ? { subject: [{ kind: sel.kind, id: sel.id, label: sel.title } as WsScreenRef], selection: [{ kind: sel.kind, id: sel.id } as WsScreenRef] } : {}),
    visible: shown.slice(0, 20).map((c) => ({ kind: c.kind, id: c.id }) as WsScreenRef),
  });

  return (
    <>
      <div className="hero-body">
        {error ? (
          <p className="hot" role="alert">
            Couldn't read the world-state. It will try again.
          </p>
        ) : narrow ? (
          <FieldList concerns={shown} now={now} selected={selected} onSelect={onSelect} />
        ) : (
          <FieldChart concerns={shown} now={now} selected={selected} onSelect={onSelect} reorder={reorder} />
        )}
        {!error && loading && <p className="muted field-note">Reading the world-state…</p>}
        {!error && !loading && concerns.length === 0 && <p className="muted field-note">Nothing tracked yet. Tell me what you are working on.</p>}
      </div>
      {!narrow && (
        <p className="legend" aria-label="How to read the field">
          <span><i className="mark filled" /> told · evidenced</span>
          <span><i className="mark half" /> inferred</span>
          <span><i className="mark dashed" /> suspected</span>
          <span><i className="mark" /> goal</span>
          <span><i className="mark hot" /> slipped</span>
          <span>dotted trail = sureness decayed as evidence aged</span>
        </p>
      )}
      {sel && (
        <FieldReadout
          concern={sel}
          now={now}
          offline={offline}
          pinOnDrop={pinOnDrop}
          onPinOnDrop={setPinOnDrop}
          onUnpin={(overrideId) => unpin.mutate({ overrideId })}
          onTransition={(loopId, kind) => transition.mutate({ loopId, kind })}
          busy={unpin.isPending || transition.isPending || reprioritize.isPending}
          error={unpin.isError || transition.isError || reprioritize.isError}
          onClose={() => onSelect(null)}
          onChatAbout={onChatAbout}
        />
      )}
    </>
  );
}
