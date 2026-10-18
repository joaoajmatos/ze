import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { ReplyActions } from "@/features/reply-feedback";
import { useTraceStore, threadTraceBucket } from "@/features/trace-state";
import { Module } from "@/shared/ui";
import { describeJudgments } from "../lib/instruments/judgments";
import { readoutsFor } from "../lib/instruments/readouts";
import { coordinateOf, routingFor } from "../lib/instruments/routing";
import type { WhySection } from "../lib/why";
import { useAssemble } from "../model/useAssemble";
import { Instrument } from "./trace/Instrument";
import { JudgmentGauges } from "./trace/JudgmentGauges";
import { MemoryConstellation } from "./trace/MemoryConstellation";
import { Readouts } from "./trace/Readouts";
import { ReversalTrack } from "./trace/ReversalTrack";
import { RoutingInstrument } from "./trace/RoutingInstrument";
import { ConductorRow } from "./trace/rows/ConductorRow";
import { ConfirmationsRow } from "./trace/rows/ConfirmationsRow";
import { ScreenRow } from "./trace/rows/ScreenRow";
import { SkillsRow } from "./trace/rows/SkillsRow";
import { SourcesRow } from "./trace/rows/SourcesRow";
import { WorkspaceRow } from "./trace/rows/WorkspaceRow";
import { SignalPath } from "./trace/SignalPath";
import { ToolsTimeline } from "./trace/ToolsTimeline";

interface TraceModuleProps {
  threadId: string;
  /** The reply to trace; the latest when omitted. A turn in flight is traced live whatever is selected. */
  messageId?: string | null;
  /** "Why?" opens the rail at a section and marks the rows that drew the reply's modules. */
  openSection?: WhySection | null;
  highlight?: string[];
}

/** The trace of one reply as a rail of instruments: calm by default, each line a readout that opens. */
export function TraceModule({ threadId, messageId = null, openSection = null, highlight = [] }: TraceModuleProps) {
  const { thread, latestId, feedbackById } = useAssemble(threadId);
  const bucket = useTraceStore((s) => threadTraceBucket(s, threadId));
  const phase = thread.turn.phase;
  const streaming = phase === "awaiting" || phase === "thinking" || phase === "speaking";
  const id = messageId ?? latestId;
  const committed = bucket.traces.find((t) => t.message_id === id);
  const live = streaming ? bucket.pendingTrace : null;
  const trace: Partial<WsTraceUpdateFrame> | null | undefined = live ?? committed;
  const arrivals = live ? bucket.pendingArrivals : id ? bucket.arrivalsByMessage[id] : undefined;
  const feedback = id ? feedbackById.get(id) : undefined;

  if (!trace) {
    return (
      <Module label="trace" headless={false}>
        <p className="muted">{streaming ? "Ze is working. The trace fills in as each step finishes." : "No trace for this reply."}</p>
      </Module>
    );
  }

  const coordinate = coordinateOf(trace);
  const routing = routingFor(trace);
  const { groups } = describeJudgments(trace.judgments);
  const readouts = readoutsFor(trace);
  const toolCalls = trace.tool_calls?.length ?? 0;
  const memoryCount = trace.memory_chunks?.length ?? 0;
  const undone = (feedback?.rollback?.entries ?? []).filter((e) => e.outcome === "undone").length;
  const full = trace as WsTraceUpdateFrame;

  return (
    <Module
      label="trace"
      tools={id && !streaming ? <ReplyActions messageId={id} feedback={feedback} /> : undefined}
    >
      {coordinate && <p className="lbl tr-coordinate">{coordinate}</p>}
      <SignalPath trace={trace} arrivals={arrivals} sentAt={thread.turn.lastSent?.at ?? null} streaming={streaming} />
      <Instrument name="Routing" readout={routing.bar?.value != null ? `${trace.agent} · ${Math.round(routing.bar.value * 100)}%` : `${trace.agent ?? ""} · ${routing.methodWords}`} open={openSection === "routing" || undefined}>
        <RoutingInstrument trace={trace} />
      </Instrument>
      {!streaming && memoryCount > 0 && (
        <Instrument name="Memory" readout={`${memoryCount} from memory`}>
          <MemoryConstellation chunks={trace.memory_chunks} />
        </Instrument>
      )}
      {toolCalls > 0 && (
        <Instrument name="Tools" readout={`${toolCalls} call${toolCalls === 1 ? "" : "s"}`} open={openSection === "tools" || undefined}>
          <ToolsTimeline trace={trace} partial={streaming} highlight={highlight} />
        </Instrument>
      )}
      {groups.length > 0 && (
        <Instrument name="Judgments" readout={readouts.systemOneText ?? `${groups.reduce((n, g) => n + g.rows.length, 0)} judgments`}>
          <JudgmentGauges trace={trace} />
        </Instrument>
      )}
      {feedback?.rollback && (
        <Instrument name="Reversal" readout={`${undone} undone`}>
          <ReversalTrack rollback={feedback.rollback} />
        </Instrument>
      )}
      {!streaming && <Readouts trace={trace} />}
      <SkillsRow skillsUsed={trace.skills_used} live={streaming} />
      <SourcesRow sources={trace.sources ?? []} />
      <WorkspaceRow workspace={trace.workspace} live={streaming} />
      {trace.conductor_hint !== undefined || trace.conductor_ledger ? <ConductorRow trace={full} live={streaming} /> : null}
      <ConfirmationsRow outcomes={trace.write_confirmations} />
      <ScreenRow screen={trace.screen} />
    </Module>
  );
}
