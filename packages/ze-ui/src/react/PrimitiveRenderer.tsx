import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { cn } from "../lib/cn";
import type {
  Badge,
  Button,
  CardAction,
  Card,
  Chart,
  ClaimCard,
  ClaimList,
  ClaimPosture,
  ClaimTimeline,
  Col,
  ConnectionItem,
  Connections,
  Form,
  EntityFacet,
  Headline,
  PrimitiveAction,
  Row,
  Spacer,
  Sparkline,
  StatRow,
  StepItem,
  Steps,
  Table,
  Text,
} from "../generated/types.gen";
import type { FallbackNode, LegacyButtonNode, RenderNode } from "../parse";
import { AreaChart, BarChart, LineChart, PieChart } from "../charts";
import {
  PrimitiveRendererContext,
  usePrimitiveRendererActions,
  type PrimitiveClassNames,
  type PrimitiveRendererActions,
} from "./context";

/** The host's class for `key`, else the renderer's own. */
function useCx() {
  const { classNames } = usePrimitiveRendererActions();
  return (key: keyof PrimitiveClassNames, fallback: string) => classNames?.[key] ?? fallback;
}

const GAP: Record<string, string> = {
  none: "gap-0",
  sm: "gap-2",
  md: "gap-4",
  lg: "gap-6",
};

const ALIGN: Record<string, string> = {
  start: "items-start",
  center: "items-center",
  end: "items-end",
  between: "justify-between items-center",
};

const COL_VARIANT: Record<string, string> = {
  default: "",
  card: "px-4 py-3.5 rounded-[20px] border border-white/10 bg-white/[0.03]",
  section:
    "px-4 py-3.5 rounded-[20px] border border-white/10 bg-white/[0.03] border-l-2 border-l-amber-spark",
};

const TEXT_STYLE: Record<string, string> = {
  heading: "text-[48px] font-extralight leading-none tracking-tight text-white",
  subheading: "text-sm font-semibold text-white",
  body: "text-sm leading-relaxed text-white",
  label: "text-xs tracking-wide text-smoke",
  caption: "text-xs text-ash",
  code: "font-mono text-xs bg-white/5 rounded px-1 py-0.5 text-white",
};

const TEXT_COLOR: Record<string, string> = {
  default: "",
  muted: "text-smoke",
  success: "text-lichen",
  warning: "text-amber-spark",
  error: "text-red-400",
};

const BADGE_COLOR: Record<string, string> = {
  default: "border-white/20 text-white",
  success: "border-lichen/50 text-lichen",
  warning: "border-amber-spark/50 text-amber-spark",
  error: "border-red-400/50 text-red-400",
  info: "border-plum-voltage/50 text-plum-voltage",
};

const RELATION_LABELS: Record<string, string> = {
  pattern: "Pattern",
  causal_guess: "Possible link",
  tension: "Tension",
  convergence: "Convergence",
};

export interface PrimitiveRendererProps {
  node: RenderNode;
  actions?: PrimitiveRendererActions;
}

export function PrimitiveRenderer({ node, actions }: PrimitiveRendererProps) {
  const content = <PrimitiveNodeRenderer node={node} />;
  if (!actions) {
    return content;
  }
  return (
    <PrimitiveRendererContext.Provider value={actions}>
      {content}
    </PrimitiveRendererContext.Provider>
  );
}

export function PrimitiveTreeRenderer({
  nodes,
  actions,
}: {
  nodes: RenderNode[];
  actions?: PrimitiveRendererActions;
}) {
  const tree = (
    <>
      {nodes.map((node, i) => (
        <PrimitiveNodeRenderer key={i} node={node} />
      ))}
    </>
  );

  if (!actions) {
    return tree;
  }

  return <PrimitiveRendererContext.Provider value={actions}>{tree}</PrimitiveRendererContext.Provider>;
}

function PrimitiveNodeRenderer({ node }: { node: RenderNode }) {
  switch (node.type) {
    case "col":
      return <ColRenderer node={node} />;
    case "row":
      return <RowRenderer node={node} />;
    case "text":
      return <TextRenderer node={node} />;
    case "badge":
      return <BadgeRenderer node={node} />;
    case "divider":
      return <DividerRenderer />;
    case "spacer":
      return <SpacerRenderer node={node} />;
    case "button":
      return <ButtonRenderer node={node} />;
    case "table":
      return <TableRenderer node={node} />;
    case "form":
      return <FormRenderer node={node} />;
    case "connections":
      return <ConnectionsRenderer node={node} />;
    case "steps":
      return <StepsRenderer node={node} />;
    case "chart":
      return <ChartRenderer node={node} />;
    case "headline":
      return <HeadlineRenderer node={node} />;
    case "claim_card":
      return <ClaimCardRenderer node={node} />;
    case "claim_timeline":
      return <ClaimTimelineRenderer node={node} />;
    case "entity_facet":
      return <EntityFacetRenderer node={node} />;
    case "stat_row":
      return <StatRowRenderer node={node} />;
    case "claim_list":
      return <ClaimListRenderer node={node} />;
    case "sparkline":
      return <SparklineRenderer node={node} />;
    case "card":
      return <CardRenderer node={node} />;
    case "__fallback":
      return <FallbackRenderer node={node} />;
    case "__legacy_button":
      return <LegacyButtonRenderer node={node} />;
    default:
      // A node that skipped parsing: show what it is instead of vanishing.
      return <FallbackRenderer node={{ type: "__fallback", original: String((node as { type?: unknown }).type), fields: [], children: [] }} />;
  }
}

const TARGET = "min-h-11 min-w-11";

function FallbackRenderer({ node }: { node: FallbackNode }) {
  const cx = useCx();
  return (
    <div className="flex flex-col gap-2">
      <div className={cx("table", "overflow-auto max-h-72 rounded-[20px] border border-white/10 bg-white/[0.02]")}>
        <p className="px-4 py-2 text-xs font-semibold tracking-widest uppercase text-smoke">
          Unsupported view: {node.original}
        </p>
        <table className="w-full text-sm">
          <thead className="sr-only">
            <tr>
              <th>Field</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {node.fields.map(([name, value]) => (
              <tr key={name} className="border-b border-white/5 last:border-0">
                <td className="px-4 py-2 text-xs text-ash whitespace-nowrap">{name}</td>
                <td className="px-4 py-2 text-white/80">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {node.children.map((child, i) => (
        <PrimitiveNodeRenderer key={i} node={child} />
      ))}
    </div>
  );
}

function LegacyButtonRenderer({ node }: { node: LegacyButtonNode }) {
  return (
    <button
      type="button"
      disabled
      title="This older button no longer works."
      className={cn(TARGET, "px-4 py-2 rounded-pill border border-white/15 text-xs font-semibold tracking-wide text-white opacity-40")}
    >
      {node.label}
    </button>
  );
}

/** Runs `action` through the host; a refusal reports the disconnect so the control stays usable. */
function useRunAction() {
  const { onAction, onDisconnected } = usePrimitiveRendererActions();
  return async (action: PrimitiveAction): Promise<boolean> => {
    let ok: boolean | void = true;
    try {
      ok = await onAction?.(action);
    } catch {
      ok = false;
    }
    if (ok === false) {
      onDisconnected?.();
      return false;
    }
    return true;
  };
}

function fillKey(action: PrimitiveAction, key: string): PrimitiveAction {
  if (action.kind !== "tool") return action;
  const args = Object.fromEntries(
    Object.entries(action.args).map(([k, v]) => [k, v === "{key}" ? key : v]),
  );
  return { ...action, args };
}

const POSTURE_TONE: Record<string, string> = {
  fact: "text-white",
  identity: "text-white",
  inference: "text-white/80",
  suspicion: "text-amber-spark",
  priority: "text-ember",
};

function postureTone(claim: ClaimPosture): string {
  return POSTURE_TONE[claim.kind ?? ""] ?? "text-white/70";
}

function EntityFacetRenderer({ node }: { node: EntityFacet }) {
  const run = useRunAction();
  return (
    <section className="flex flex-col gap-2 rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-3.5">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-smoke">{node.title}</p>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {node.facts.map((fact, i) => (
          <li key={i} data-kind={fact.claim.kind ?? fact.claim.subject} className="flex flex-col">
            <span className={cn("text-sm", postureTone(fact.claim))}>{fact.text}</span>
            <span className="text-[11px] text-white/45">
              {[postureLine(fact.claim), fact.source, fact.at?.slice(0, 10)].filter(Boolean).join(" · ")}
            </span>
          </li>
        ))}
      </ul>
      {node.more && (
        <button
          type="button"
          onClick={() => void run(node.more!)}
          className={cn(TARGET, "self-start px-3 rounded-pill border border-white/15 text-xs hover:bg-white/5")}
        >
          More
        </button>
      )}
    </section>
  );
}

const DIRECTION_LABEL = { up: "up", down: "down", flat: "no change" } as const;
const DIRECTION_MARK = { up: "▲", down: "▼", flat: "–" } as const;

function StatRowRenderer({ node }: { node: StatRow }) {
  return (
    <dl className="m-0 grid grid-cols-2 gap-3 sm:grid-cols-3">
      {node.items.map((item, i) => (
        <div key={i} className="flex flex-col rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-3">
          <dt className="text-xs text-smoke">{item.label}</dt>
          <dd className="m-0 text-xl font-light text-white">{item.value}</dd>
          {item.delta && (
            <dd className="m-0 text-xs text-white/60">
              {item.direction && <span aria-hidden="true">{DIRECTION_MARK[item.direction]} </span>}
              <span>{item.delta}</span>
              {item.direction && <span className="sr-only"> ({DIRECTION_LABEL[item.direction]})</span>}
            </dd>
          )}
        </div>
      ))}
    </dl>
  );
}

function ClaimListRenderer({ node }: { node: ClaimList }) {
  const run = useRunAction();
  return (
    <section className="flex flex-col gap-1">
      {node.title && <p className="text-xs text-white/60">{node.title}</p>}
      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {node.items.map((item, i) => (
          <li
            key={i}
            data-kind={item.claim.kind ?? item.claim.subject}
            className="flex flex-col rounded-lg border border-white/10 px-3 py-1"
          >
            {item.action ? (
              <button
                type="button"
                onClick={() => void run(item.action!)}
                className={cn(TARGET, "flex flex-col items-start text-left text-sm hover:bg-white/5", postureTone(item.claim))}
              >
                {item.text}
                <span className="text-[11px] text-white/45">{postureLine(item.claim)}</span>
              </button>
            ) : (
              <>
                <span className={cn("text-sm", postureTone(item.claim))}>{item.text}</span>
                <span className="text-[11px] text-white/45">{postureLine(item.claim)}</span>
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

const SPARK_W = 120;
const SPARK_H = 28;

function SparklineRenderer({ node }: { node: Sparkline }) {
  const points = node.points.slice(0, 60);
  const min = Math.min(...points);
  const span = Math.max(...points) - min || 1;
  const step = points.length > 1 ? SPARK_W / (points.length - 1) : 0;
  const coords = points
    .map((p, i) => `${(i * step).toFixed(1)},${(SPARK_H - ((p - min) / span) * (SPARK_H - 2) - 1).toFixed(1)}`)
    .join(" ");
  return (
    <div className="flex items-center gap-3">
      <div className="flex flex-col">
        <span className="text-xs text-smoke">{node.label}</span>
        {node.value && <span className="text-sm text-white">{node.value}</span>}
      </div>
      {points.length > 0 && (
        <svg role="img" aria-label={`${node.label} trend`} viewBox={`0 0 ${SPARK_W} ${SPARK_H}`} className="h-7 w-[120px]">
          <polyline points={coords} fill="none" stroke="currentColor" strokeWidth="1.5" className="text-plum-voltage" />
        </svg>
      )}
    </div>
  );
}

function CardRenderer({ node }: { node: Card }) {
  const cx = useCx();
  return (
    <section className={cx("card", "flex flex-col gap-2 rounded-[20px] border border-white/10 bg-white/[0.03] px-4 py-3.5")}>
      <p className="text-sm font-semibold text-white">{node.title}</p>
      {node.body && <p className="text-sm text-white/70">{renderInlineMarkdown(node.body)}</p>}
      {node.children.map((child, i) => (
        <PrimitiveNodeRenderer key={i} node={child} />
      ))}
      {node.actions && node.actions.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-1">
          {node.actions.map((button, i) => (
            <ButtonRenderer key={i} node={button} />
          ))}
        </div>
      )}
    </section>
  );
}

function DividerRenderer() {
  const cx = useCx();
  return <hr className={cx("divider", "border-white/10 my-1")} />;
}

function ColRenderer({ node }: { node: Col }) {
  const cx = useCx();
  const variant = node.variant ?? "default";
  const variantClass = variant === "default" ? "" : cx("card", COL_VARIANT[variant]);
  return (
    <div className={cn("flex flex-col", GAP[node.gap ?? "sm"], variantClass)}>
      {node.children.map((child, i) => (
        <PrimitiveNodeRenderer key={i} node={child} />
      ))}
    </div>
  );
}

function RowRenderer({ node }: { node: Row }) {
  return (
    <div className={cn("flex flex-row flex-wrap", GAP[node.gap ?? "sm"], ALIGN[node.align ?? "start"])}>
      {node.children.map((child, i) => (
        <PrimitiveNodeRenderer key={i} node={child} />
      ))}
    </div>
  );
}

// Agents emit light markdown in text bodies; render the inline subset instead of
// showing raw ** / ` markers. Block markdown is out of scope for primitives.
const INLINE_MD = /(\*\*[^*\n]+\*\*|\*[^*\n]+\*|`[^`\n]+`)/g;

function renderInlineMarkdown(content: string): ReactNode[] {
  return content.split(INLINE_MD).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      return <em key={i}>{part.slice(1, -1)}</em>;
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return (
        <code key={i} className="font-mono text-xs bg-white/5 rounded px-1 py-0.5">
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}

function TextRenderer({ node }: { node: Text }) {
  const cx = useCx();
  const style = (node.style ?? "body") as keyof typeof TEXT_STYLE;
  const styleClass = cx(style as keyof PrimitiveClassNames, TEXT_STYLE[style] ?? TEXT_STYLE.body);
  const colorClass =
    node.color === "muted" ? cx("muted", TEXT_COLOR.muted) : node.color && node.color !== "default" ? TEXT_COLOR[node.color] : "";
  return (
    <p className={cn(styleClass, colorClass)}>{renderInlineMarkdown(node.content)}</p>
  );
}

function BadgeRenderer({ node }: { node: Badge }) {
  const cx = useCx();
  const colorClass = BADGE_COLOR[node.color ?? "default"] ?? BADGE_COLOR.default;
  const mapped = cx("badge", "");
  return (
    <span className={mapped ? cn(mapped, node.color && node.color !== "default" && `is-${node.color}`) : cn("px-2 py-0.5 rounded-full border text-xs flex-shrink-0", colorClass)}>
      {node.label}
    </span>
  );
}

function SpacerRenderer({ node }: { node: Spacer }) {
  const h = node.size === "lg" ? "h-6" : node.size === "sm" ? "h-1" : "h-3";
  return <div className={h} />;
}

function ButtonRenderer({ node }: { node: Button }) {
  const { onAction, onDisconnected } = usePrimitiveRendererActions();
  const cx = useCx();
  const [used, setUsed] = useState(false);

  async function handleClick() {
    if (used) return;
    let ok: boolean | void = true;
    try {
      ok = await onAction?.(node.action);
    } catch {
      ok = false;
    }
    if (ok === false) {
      onDisconnected?.();
      return;
    }
    setUsed(true);
  }

  const styleClass =
    node.style === "primary"
      ? "bg-plum-voltage text-white hover:bg-plum-voltage/85"
      : node.style === "danger"
        ? "border border-ember/50 text-ember hover:bg-ember/10"
        : "border border-white/15 text-white hover:bg-white/5";

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={used}
      className={
        cx("button", "")
          ? cn(
              TARGET,
              cx("button", ""),
              node.style === "primary" && cx("buttonPrimary", ""),
              node.style === "danger" && cx("buttonDanger", ""),
            )
          : cn(
              TARGET,
              "px-4 py-2 rounded-pill text-xs font-semibold tracking-wide cursor-pointer",
              "transition-[background-color,opacity] duration-250 disabled:opacity-40 disabled:cursor-default",
              styleClass,
              used && "opacity-100",
            )
      }
    >
      {used ? `✓ ${node.label}` : node.label}
    </button>
  );
}

function TableRenderer({ node }: { node: Table }) {
  const cx = useCx();
  const run = useRunAction();
  const rowActions = node.row_actions ?? [];
  return (
    <div className={cx("table", "overflow-auto max-h-72 rounded-[20px] border border-white/10 bg-white/[0.02]")}>
      {node.title && (
        <p className="px-4 py-2 text-xs font-semibold tracking-widest uppercase text-smoke">
          {node.title}
        </p>
      )}
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/10">
            {node.headers.map((h) => (
              <th
                key={h}
                className="px-4 py-2 text-left text-xs font-semibold tracking-wide text-ash whitespace-nowrap"
              >
                {h}
              </th>
            ))}
            {rowActions.length > 0 && (
              <th className="px-4 py-2">
                <span className="sr-only">Actions</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {node.rows.map((row, i) => (
            <tr key={i} className="border-b border-white/5 last:border-0">
              {row.map((cell, j) => (
                <td key={j} className="px-4 py-2 text-white/80 whitespace-nowrap">
                  {cell}
                </td>
              ))}
              {rowActions.length > 0 && (
                <td className="px-4 py-1 whitespace-nowrap">
                  {node.keys?.[i] !== undefined &&
                    rowActions.map((rowAction, k) => (
                      <button
                        key={k}
                        type="button"
                        onClick={() => void run(fillKey(rowAction.action, node.keys![i]!))}
                        className={cn(TARGET, "px-3 rounded-pill border border-white/15 text-xs text-white hover:bg-white/5")}
                      >
                        {rowAction.label}
                      </button>
                    ))}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {node.caption && <p className="px-4 py-2 text-xs text-smoke">{node.caption}</p>}
    </div>
  );
}

function FormRenderer({ node }: { node: Form }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);
  const { onFormSubmit, onDisconnected } = usePrimitiveRendererActions();

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (submitted) return;
    setSubmitted(true);

    const ok = onFormSubmit?.(node.id, values);
    if (ok === false) {
      setSubmitted(false);
      onDisconnected?.();
    }
  }

  return (
    <form onSubmit={handleSubmit} className="p-4 rounded-[20px] border border-white/10 bg-white/[0.03] space-y-3">
      <p className="text-sm font-semibold text-white">{node.title}</p>
      {node.fields.map((field) => (
        <div key={field.id}>
          <label className="block text-xs text-smoke mb-1 tracking-wide">{field.label}</label>
          {field.field_type === "select" ? (
            <select
              value={values[field.id] ?? ""}
              onChange={(e) => setValues((v) => ({ ...v, [field.id]: e.target.value }))}
              disabled={submitted}
              className="min-h-11 w-full bg-transparent border border-white/20 rounded-pill px-3 py-2 text-sm text-white focus:outline-none focus:border-plum-voltage disabled:opacity-40"
            >
              <option value="">Select…</option>
              {field.options?.map((o) => (
                <option key={o} value={o} className="bg-black">
                  {o}
                </option>
              ))}
            </select>
          ) : (
            <input
              type={field.field_type ?? "text"}
              placeholder={field.placeholder ?? undefined}
              value={values[field.id] ?? ""}
              onChange={(e) => setValues((v) => ({ ...v, [field.id]: e.target.value }))}
              disabled={submitted}
              className="w-full bg-transparent border border-white/20 rounded-pill px-3 py-2 text-sm text-white placeholder-smoke focus:outline-none focus:border-plum-voltage disabled:opacity-40"
            />
          )}
        </div>
      ))}
      <button
        type="submit"
        disabled={submitted}
        className="min-h-11 w-full py-2 rounded-pill bg-plum-voltage text-white text-xs font-semibold tracking-widest uppercase disabled:opacity-40 transition-opacity"
      >
        {submitted ? "Submitted" : "Submit"}
      </button>
    </form>
  );
}

function ConnectionCard({ item }: { item: ConnectionItem }) {
  const rel = RELATION_LABELS[item.relation] ?? item.relation;
  return (
    <div className="px-4 py-3 border-b border-white/5 last:border-0">
      <div className="flex items-start gap-2 mb-1">
        <span className="flex-shrink-0 mt-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium tracking-wide uppercase border border-plum-voltage/40 text-plum-voltage">
          {rel}
        </span>
        <p className="text-sm text-white leading-snug">{item.summary}</p>
      </div>
      <p className="text-xs text-smoke leading-relaxed mb-2">{item.narrative}</p>
      {item.evidence && item.evidence.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {item.evidence.map((ev, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-white/5 text-[11px] text-smoke"
            >
              {ev.label}
              {ev.date && <span className="text-white/30">· {ev.date}</span>}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

const STEP_LABEL: Record<string, string> = {
  done: "text-sm text-ash",
  active: "text-sm font-medium text-white",
  pending: "text-sm text-smoke",
  error: "text-sm text-ember",
};

function StepMarker({ status }: { status: string }) {
  if (status === "done") {
    return (
      <span className="flex h-[18px] w-[18px] flex-shrink-0 items-center justify-center rounded-full border border-lichen/50 bg-lichen/15 text-lichen">
        <svg viewBox="0 0 10 10" className="h-2.5 w-2.5" fill="none" aria-hidden="true">
          <path d="M1.5 5.5L4 8L8.5 2.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    );
  }
  if (status === "active") {
    return (
      <span className="flex h-[18px] w-[18px] flex-shrink-0 items-center justify-center rounded-full border border-plum-voltage bg-plum-voltage/15">
        <span className="h-1.5 w-1.5 rounded-full bg-plum-voltage motion-safe:animate-pulse" />
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="flex h-[18px] w-[18px] flex-shrink-0 items-center justify-center rounded-full border border-ember/50 bg-ember/10 text-ember">
        <svg viewBox="0 0 10 10" className="h-2 w-2" fill="none" aria-hidden="true">
          <path d="M2 2L8 8M8 2L2 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      </span>
    );
  }
  return (
    <span className="h-[18px] w-[18px] flex-shrink-0 rounded-full border border-white/20" />
  );
}

function StepsRenderer({ node }: { node: Steps }) {
  const cx = useCx();
  return (
    <div className={cx("steps", "px-4 py-3.5 rounded-[20px] border border-white/10 bg-white/[0.03]")}>
      {node.title && (
        <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-smoke">
          {node.title}
        </p>
      )}
      <ol className="m-0 list-none p-0">
        {node.steps.map((step, i) => (
          <StepRow key={i} step={step} last={i === node.steps.length - 1} />
        ))}
      </ol>
    </div>
  );
}

function StepRow({ step, last }: { step: StepItem; last: boolean }) {
  const labelClass = STEP_LABEL[step.status] ?? STEP_LABEL.pending;
  return (
    <li className="relative flex gap-3 pb-3.5 last:pb-0">
      {!last && (
        <span
          aria-hidden="true"
          className={cn(
            "absolute left-[8.5px] top-[21px] bottom-[3px] w-px",
            step.status === "done" ? "bg-lichen/30" : "bg-white/10",
          )}
        />
      )}
      <span className="mt-px">
        <StepMarker status={step.status} />
      </span>
      <div className="min-w-0">
        <p className={labelClass}>
          {step.label}
          <span className="sr-only"> — {step.status}</span>
        </p>
        {step.note && <p className="mt-0.5 text-xs text-smoke">{renderInlineMarkdown(step.note)}</p>}
      </div>
    </li>
  );
}

function ChartRenderer({ node }: { node: Chart }) {
  const props = {
    data: node.data,
    seriesLabels: node.series_labels,
    xLabel: node.x_label,
    yLabel: node.y_label,
    title: node.title,
  };
  switch (node.chart_type) {
    case "line":
      return <LineChart {...props} />;
    case "bar":
      return <BarChart {...props} />;
    case "area":
      return <AreaChart {...props} />;
    case "pie":
      return <PieChart {...props} />;
    default:
      // Unsupported chart_type from a newer backend — degrade gracefully (FR-005).
      return null;
  }
}

function ConnectionsRenderer({ node }: { node: Connections }) {
  const cx = useCx();
  return (
    <div className={cx("connections", "rounded-[20px] border border-plum-voltage/20 bg-white/[0.02] overflow-hidden")}>
      <p className="px-4 py-2 text-xs font-semibold tracking-widest uppercase text-plum-voltage border-b border-plum-voltage/20">
        {node.title ?? "Connected to your history"}
      </p>
      {node.connections.map((item, i) => (
        <ConnectionCard key={i} item={item} />
      ))}
    </div>
  );
}

// Posture comes from the record, never the model. A host `classNames` map restyles the card.
const CARD_TONE: Record<NonNullable<ClaimCard["tone"]>, string> = {
  default: "border-white/10",
  cream: "border-white/30 bg-white/[0.05]",
  hot: "border-ember/60",
  dotted: "border-dashed border-white/25",
};

function postureLine(claim: ClaimCard["claim"]): string {
  const parts: string[] = [claim.kind ?? claim.subject.replace("_", " ")];
  if (claim.state) parts.push(claim.state.replace("_", " "));
  if (claim.confidence != null) parts.push(`${Math.round(claim.confidence * 100)}%`);
  if (claim.slipped) parts.push("slipped");
  return parts.join(" · ");
}

function HeadlineRenderer({ node }: { node: Headline }) {
  const { renderHeadline } = usePrimitiveRendererActions();
  if (renderHeadline) return <>{renderHeadline(node.text)}</>;
  return <p className="text-sm font-semibold tracking-widest">{node.text}</p>;
}

function ClaimCardRenderer({ node }: { node: ClaimCard }) {
  const { onCardAction, onChatAbout } = usePrimitiveRendererActions();
  const cx = useCx();
  const root = useRef<HTMLDivElement>(null);
  const [decided, setDecided] = useState(false);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const actions = (node.actions ?? []).filter((a) => !decided || a.intent === "open");
  return (
    <div
      ref={root}
      data-tone={node.tone ?? "default"}
      className={
        cx("claimCard", "")
          ? cn("claim-card", cx("claimCard", ""))
          : cn("claim-card rounded-lg border p-3 flex flex-col gap-1", CARD_TONE[node.tone ?? "default"])
      }
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium">{node.title}</p>
        {onChatAbout && node.claim.subject !== "person" && (
          <button
            type="button"
            className={cn(TARGET, "chat-about")}
            aria-label={`Chat about ${node.title}`}
            onClick={() =>
              root.current &&
              onChatAbout({ subject: node.claim.subject, ref_id: node.claim.ref_id, title: node.title, element: root.current })
            }
          >
            [ chat about this ]
          </button>
        )}
      </div>
      <p className="text-[11px] text-white/45">{postureLine(node.claim)}</p>
      {node.lines?.map((line, i) => (
        <p key={i} className="text-xs text-white/60">
          {line}
        </p>
      ))}
      {node.progress_total != null && (
        <p className="text-xs text-white/60">
          {node.progress_done ?? 0}/{node.progress_total}
        </p>
      )}
      {node.readouts && node.readouts.length > 0 && (
        <dl className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {node.readouts.map((readout, i) => (
            <div key={i} className="flex gap-1">
              <dt className="text-white/50">{readout.label}</dt>
              <dd className={cn(readout.tone === "hot" && "text-ember")}>{readout.value}</dd>
            </div>
          ))}
        </dl>
      )}
      {decided && <p className="text-xs text-white/50">Sent.</p>}
      {failed && <p className="text-xs text-ember">Could not send. Try again.</p>}
      {actions.length > 0 && (
        <div className="flex gap-2 pt-1">
          {actions.map((action: CardAction, i) => (
            <button
              key={i}
              type="button"
              disabled={pending}
              onClick={async () => {
                const event = {
                  intent: action.intent,
                  ref_id: action.ref_id,
                  subject: node.claim.subject,
                };
                if (action.intent === "open") {
                  void onCardAction?.(event);
                  return;
                }
                setPending(true);
                setFailed(false);
                let accepted: boolean | void = true;
                try {
                  accepted = await onCardAction?.(event);
                } catch {
                  accepted = false;
                }
                setPending(false);
                if (accepted === false) setFailed(true);
                else setDecided(true);
              }}
              className={cn(TARGET, "px-3 py-1 rounded-pill border border-white/15 text-xs hover:bg-white/5 cursor-pointer disabled:opacity-50 disabled:cursor-default")}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ClaimTimelineRenderer({ node }: { node: ClaimTimeline }) {
  const cx = useCx();
  return (
    <div className={cx("claimTimeline", "flex flex-col gap-1")}>
      <p className="text-xs text-white/60">{node.title}</p>
      <ol className="flex flex-col gap-1 text-xs">
        {node.entries.map((entry, i) => (
          <li key={i}>
            {entry.title}
            {entry.due_at ? ` · ${entry.due_at.slice(0, 10)}` : ""}
          </li>
        ))}
      </ol>
    </div>
  );
}
