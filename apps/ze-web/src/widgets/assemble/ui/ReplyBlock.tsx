import type { MessageSchema as Message, WsScreenRef, WsTraceUpdateFrame } from "@myguyze/ze-client";
import { useRef, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import { ConnectedPrimitiveTree } from "@/features/primitive-tree";
import { Module } from "@/shared/ui";
import { componentType, instrumentId, spanOf } from "../lib/exchanges";
import type { WhyTarget } from "../lib/why";
import { useCascade } from "./useCascade";
import { WhyLink } from "./WhyLink";

export interface ModuleKey {
  key: string;
  messageId: string;
  index: number;
  n: number;
}

interface ReplyBlockProps {
  message: Message;
  compact: boolean;
  live: boolean;
  /** Called once the fly-out starts, so a remount never replays it. */
  onPlayed?: () => void;
  /** Running A·NN number of this reply's first module on the canvas. */
  firstNumber: number;
  hidden: Set<string>;
  pinned: Set<string>;
  onPin: (key: string) => void;
  onDismiss: (key: string) => void;
  onChatAbout?: (ref: WsScreenRef, element: Element) => void;
  selected: boolean;
  onSelect?: (id: string) => void;
  trace?: WsTraceUpdateFrame;
  onWhy?: (messageId: string, target: WhyTarget) => void;
  below?: ReactNode;
}

type Component = { type?: string; title?: string; tone?: string; claim?: { subject?: string; ref_id?: string }; text?: string };

export function labelOf(component: Component): string {
  if (component.title) return component.title;
  const type = componentType(component);
  return type.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

export function chatAboutRef(component: Component): WsScreenRef | null {
  const claim = component.claim;
  if (!claim?.subject || !claim.ref_id || claim.subject === "person") return null;
  return { kind: claim.subject, id: claim.ref_id, label: labelOf(component), component: componentType(component) };
}

const TONES = new Set(["cream", "dotted"]);

/** Coral ("hot") only follows a claim, whose posture code sets; a bare model-emitted tone never paints a module coral. */
function toneOf(component: Component): "cream" | "hot" | "dotted" | "default" {
  if (component.tone === "hot" && component.claim) return "hot";
  return TONES.has(component.tone ?? "") ? (component.tone as "cream" | "dotted") : "default";
}

/** One reply: the sentence, then a module per top-level component. */
export function ReplyBlock({ message, compact, live, onPlayed, firstNumber, hidden, pinned, onPin, onDismiss, onChatAbout, selected, onSelect, trace, onWhy, below }: ReplyBlockProps) {
  const root = useRef<HTMLDivElement>(null);
  useCascade(root, live, onPlayed);
  const components = (message.components ?? []) as Component[];

  return (
    <div ref={root} className="contents">
      {(message.text || components.length > 0) && (
        <div className={`cell span-12 ${selected ? "is-selected" : ""}`}>
          {message.text && (
            <div className="assemble-sentence sentence">
              <ReactMarkdown>{message.text}</ReactMarkdown>
            </div>
          )}
          {onSelect && (
            <button type="button" className="ctl-text assemble-why" aria-pressed={selected} onClick={() => onSelect(message.id)}>
              <span className="lbl">{selected ? "tracing this reply" : "trace this reply"}</span>
            </button>
          )}
          {onWhy && <WhyLink trace={trace} onOpen={(target) => onWhy(message.id, target)} />}
          {below}
        </div>
      )}
      {components.map((component, i) => {
        const key = `${message.id}:${i}`;
        if (hidden.has(key) || pinned.has(key)) return null;
        const type = componentType(component);
        const label = labelOf(component);
        const ref = onChatAbout ? chatAboutRef(component) : null;
        return (
          <div key={key} className={`cell span-${spanOf(type, compact)}`} data-type={type} data-cascade="">
            <Module
              label={label}
              index={instrumentId(firstNumber + i)}
              tone={toneOf(component)}
              tools={<ModuleTools label={label} pinned={false} onPin={() => onPin(key)} onDismiss={() => onDismiss(key)} />}
              onChatAbout={ref && onChatAbout ? (el) => onChatAbout(ref, el) : undefined}
              chatAboutLabel={label}
            >
              <ConnectedPrimitiveTree components={[component]} />
            </Module>
          </div>
        );
      })}
    </div>
  );
}

export function ModuleTools({ label, pinned, onPin, onDismiss }: { label: string; pinned: boolean; onPin: () => void; onDismiss: () => void }) {
  return (
    <span className="tools">
      <button type="button" className="tool" aria-pressed={pinned} aria-label={`${pinned ? "Unpin" : "Pin"} ${label}`} onClick={onPin}>
        {pinned ? "unpin" : "pin"}
      </button>
      <button type="button" className="tool" aria-label={`Dismiss ${label}`} onClick={onDismiss}>
        ✕
      </button>
    </span>
  );
}
