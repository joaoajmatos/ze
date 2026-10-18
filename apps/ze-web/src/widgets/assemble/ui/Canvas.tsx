import type { WsScreenRef } from "@myguyze/ze-client";
import { useCallback, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { ConnectedPrimitiveTree } from "@/features/primitive-tree";
import { ReplyActions } from "@/features/reply-feedback";
import { useScreenPublisher } from "@/entities/screen-context";
import { Module } from "@/shared/ui";
import { componentType, instrumentId, spanOf } from "../lib/exchanges";
import type { WhyTarget } from "../lib/why";
import { useAssemble } from "../model/useAssemble";
import { DeliveryFailedRow } from "./DeliveryFailedRow";
import { chatAboutRef, labelOf, ModuleTools, ReplyBlock } from "./ReplyBlock";

export interface CanvasProps {
  threadId: string;
  /** The overlay and phones: every module spans all 12 columns. */
  compact?: boolean;
  /** The reply whose trace the page shows. */
  selectedMessageId?: string | null;
  onSelect?: (messageId: string) => void;
  onChatAbout?: (ref: WsScreenRef, element: Element) => void;
  /** "Why?" on a reply: the page or overlay opens the trace at that section. */
  onWhy?: (messageId: string, target: WhyTarget) => void;
  /** Messages already in the thread that this view leaves out (the overlay shows only what came after it opened). */
  hiddenMessageIds?: ReadonlySet<string> | null;
}

const DISCLOSURE = "Ze is AI and can make mistakes.";

/** The Assemble canvas: each exchange is the person's line, then Ze's reply as a sentence and a module per component. */
export function Canvas({ threadId, compact = false, selectedMessageId = null, onSelect, onChatAbout, onWhy, hiddenMessageIds }: CanvasProps) {
  const { thread, exchanges, latestId, feedbackById, traceBucket } = useAssemble(threadId, hiddenMessageIds);
  const [pinned, setPinned] = useState<Set<string>>(new Set());
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  // Replies already in the thread when it loaded appear at once; only a reply that arrives live cascades.
  const known = useRef<Set<string> | null>(null);
  const live = useRef<Set<string>>(new Set());
  const replies = exchanges.flatMap((e) => e.replies);
  if (thread.historyLoaded && known.current === null) known.current = new Set(replies.map((r) => r.id));
  if (known.current) {
    for (const r of replies) {
      if (!known.current.has(r.id)) {
        known.current.add(r.id);
        live.current.add(r.id);
      }
    }
  }
  const seenThread = useRef(threadId);
  if (seenThread.current !== threadId) {
    seenThread.current = threadId;
    known.current = null;
    live.current = new Set();
  }

  const toggle = (setter: typeof setPinned) => (key: string) =>
    setter((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  const pin = useCallback(toggle(setPinned), []);
  const dismiss = useCallback(
    (key: string) => {
      setHidden((prev) => new Set(prev).add(key));
      setPinned((prev) => {
        if (!prev.has(key)) return prev;
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    },
    [],
  );

  // Running A·NN numbers over the whole canvas, so ids are unique.
  const numbering = useMemo(() => {
    let n = 1;
    const first = new Map<string, number>();
    for (const r of replies) {
      first.set(r.id, n);
      n += (r.components ?? []).length;
    }
    return first;
  }, [replies]);

  const pinnedModules = replies.flatMap((r) =>
    ((r.components ?? []) as Record<string, unknown>[]).map((component, i) => ({ r, component, i, key: `${r.id}:${i}` })).filter((m) => pinned.has(m.key) && !hidden.has(m.key)),
  );

  const [focusedModule, setFocusedModule] = useState<string | undefined>();
  useScreenPublisher({
    focused_module: focusedModule,
    canvas: replies.flatMap((r) =>
      ((r.components ?? []) as Record<string, unknown>[]).map((component, i) => {
        const ref = chatAboutRef(component);
        return { index: (numbering.get(r.id) ?? 1) + i, type: componentType(component), ...(ref ? { ref: { kind: ref.kind, id: ref.id } } : {}) };
      }),
    ),
  });

  const phase = thread.turn.phase;
  const firstReplyId = replies[0]?.id ?? null;
  const streaming = (phase === "speaking" && thread.turn.streamingText) || null;
  const working = phase === "awaiting" || phase === "thinking";

  return (
    <div
      className={`assemble ${compact ? "compact" : ""}`}
      onFocusCapture={(e) => {
        const id = (e.target as Element).closest(".mod")?.querySelector(".idx")?.textContent;
        if (id) setFocusedModule(id);
      }}
    >
      {pinnedModules.length > 0 && (
        <div className="canvas assemble-pinned">
          {pinnedModules.map(({ r, component, i, key }) => {
            const label = labelOf(component);
            return (
              <div key={key} className={`cell span-${spanOf(componentType(component), compact)}`} data-type={componentType(component)}>
                <Module label={label} index={instrumentId((numbering.get(r.id) ?? 1) + i)} tools={<ModuleTools label={label} pinned onPin={() => pin(key)} onDismiss={() => dismiss(key)} />}>
                  <ConnectedPrimitiveTree components={[component]} />
                </Module>
              </div>
            );
          })}
        </div>
      )}
      {exchanges.map((exchange, ei) => (
        <section key={exchange.id} className="assemble-exchange" aria-label="Exchange">
          {exchange.user && <p className="assemble-you">{exchange.user.text}</p>}
          {exchange.unprompted && <p className="lbl assemble-origin">Ze, unprompted</p>}
          <div className="canvas">
            {exchange.replies.map((reply) => (
              <ReplyBlock
                key={reply.id}
                message={reply}
                compact={compact}
                live={live.current.has(reply.id)}
                firstNumber={numbering.get(reply.id) ?? 1}
                hidden={hidden}
                pinned={pinned}
                onPin={pin}
                onDismiss={dismiss}
                onChatAbout={onChatAbout}
                selected={selectedMessageId === reply.id}
                onSelect={onSelect}
                trace={traceBucket.traces.find((t) => t.message_id === reply.id)}
                onWhy={onWhy}
                below={
                  <>
                    {reply.id === firstReplyId && <p className="lbl assemble-disclosure">{DISCLOSURE}</p>}
                    {reply.id === latestId && (
                      <div className="group/reply">
                        <ReplyActions messageId={reply.id} feedback={feedbackById.get(reply.id)} />
                      </div>
                    )}
                  </>
                }
              />
            ))}
            {ei === exchanges.length - 1 && (streaming || working) && (
              <div className="cell span-12">
                <div className="assemble-sentence sentence" aria-live="polite">
                  {streaming ? <ReactMarkdown>{streaming}</ReactMarkdown> : <span className="lbl on">{thread.turn.typingText ?? "thinking"}</span>}
                </div>
              </div>
            )}
          </div>
        </section>
      ))}
      {phase === "failed" && <DeliveryFailedRow threadId={threadId} />}
    </div>
  );
}
