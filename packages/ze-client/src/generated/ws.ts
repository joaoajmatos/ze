/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsInboundFrame".
 */
export type WsInboundFrame =
  | WsMessageFrame
  | WsEditFrame
  | WsConfirmRequestFrame
  | WsConfirmCancelFrame
  | WsTypingFrame
  | WsTokenFrame
  | WsErrorFrame
  | WsMessageSupersededFrame
  | WsRefreshFrame
  | WsPongFrame
  | WsTraceUpdateFrame
  | WsNotificationFrame;
export type Type = "message";
export type Id = string;
export type Role = "user" | "assistant";
export type Text = string | null;
export type Components = {
  [k: string]: unknown;
}[];
export type Read = boolean;
export type ThreadId = string | null;
export type CreatedAt = string;
export type Replaces = string | null;
export type ReplacedBy = string | null;
export type SessionId = string;
export type Completed = boolean;
export type Type1 = "edit";
export type Id1 = string;
export type ThreadId1 = string | null;
export type Text1 = string | null;
export type Components1 = {
  [k: string]: unknown;
}[];
export type Type2 = "confirm_request";
export type Id2 = string;
export type ThreadId2 = string | null;
export type Kind = "write" | "budget" | "held";
export type Round = number;
export type Title = string;
export type ItemId = string;
export type Agent = string;
export type Tool = string | null;
export type EffectPhrase = string;
export type Summary = string;
export type Conflict = string | null;
export type EditableField = string | null;
export type ProposedText = string | null;
export type Items = WsConfirmItem[];
export type Kind1 = "workflow" | "goal";
export type Name = string;
export type ExpiresAt = string | null;
export type Label = string;
export type Value = string;
export type Style = ("primary" | "secondary" | "danger") | null;
export type Actions = WsConfirmAction[];
export type Type3 = "confirm_cancel";
export type Id3 = string;
export type ThreadId3 = string | null;
export type Type4 = "typing";
export type ThreadId4 = string | null;
export type Text2 = string | null;
export type Type5 = "token";
export type ThreadId5 = string | null;
export type Text3 = string;
export type Type6 = "error";
export type ThreadId6 = string | null;
export type Detail = string;
export type Code = ("busy" | "retry_unavailable" | "retry_failed") | null;
export type MessageId = string | null;
export type ReasonCode = string | null;
export type ReasonText = string | null;
export type Type7 = "message_superseded";
export type ThreadId7 = string | null;
export type MessageId1 = string;
export type ReplacedBy1 = string;
export type Type8 = "refresh";
export type ThreadId8 = string | null;
export type Screen = string;
export type Type9 = "pong";
export type Type10 = "trace_update";
export type ThreadId9 = string;
export type MessageId2 = string;
export type Partial = boolean;
export type Agent1 = string;
export type RoutingMethod = string;
export type Confidence = number;
export type ScoreGap = number;
export type IsCompound = boolean;
export type Subtasks = string[];
export type Text4 = string;
export type Score = number;
export type Source = string;
export type ExtractionConfidence = number | null;
export type MemoryChunks = MemoryChunkTraceResponse[];
export type Name1 = string;
export type ResultSnippet = string;
export type DurationMs = number;
export type Success = boolean;
export type Access = "read" | "write" | "delegate" | "unknown";
export type Reversibility = ("reversible" | "irreversible") | null;
export type UndoTool = string | null;
export type Gate = "none" | "approved" | "pre_approved" | "denied" | "refused_over_cap" | "expired";
export type EffectPhrase1 = string | null;
export type ToolCalls = ToolCallTraceResponse[];
export type TotalDurationMs = number;
export type SkillId = string;
export type Name2 = string;
export type Source1 = string;
export type Trigger = string;
export type Similarity = number | null;
export type ScriptRan = boolean;
export type BelowFloor = boolean;
export type SkillsUsed = SkillUsageTraceResponse[];
export type Command = string;
export type Success1 = boolean;
export type Status = "in_progress" | null;
export type Id4 = string | null;
export type Runs = WorkspaceRunTraceResponse[];
export type Path = string;
export type Op = "read" | "write" | "delete" | "ingest";
export type Files = WorkspaceFileTraceResponse[];
export type ScriptRan1 = boolean;
export type Unavailable = boolean;
export type Planned = string[] | null;
export type InvocationId = string;
export type ProcedureId = string;
export type VersionId = string;
export type ConductorHint =
  | {
      [k: string]: string;
    }[]
  | null;
export type Agent2 = string;
export type Status1 = string;
export type RequestId = string | null;
export type ConductorLedger = ConductorLedgerEntryResponse[];
export type QuestionId = string;
export type Kind2 = string;
export type LatencyMs = number;
export type Answer = string | number | null;
export type Probabilities = {
  [k: string]: number;
} | null;
export type Peakedness = number | null;
export type Model = string | null;
export type InputTokens = number | null;
export type Consumed = boolean;
export type SkipReason = string | null;
export type Judgments = JudgmentTraceResponse[];
export type Url = string;
export type Title1 = string;
export type Sources = SourceTraceResponse[];
export type EffectsKnown = boolean;
export type Type11 = "notification";
export type Id5 = string;
export type EventType = string;
export type Source2 = string;
export type Title2 = string;
export type Body = string;
export type TargetType = string | null;
export type TargetId = string | null;
export type CreatedAt1 = string;
export type Read1 = boolean;
export type PushClass = string;
export type Delivery = string;
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsOutboundFrame".
 */
export type WsOutboundFrame =
  | WsSendMessageFrame
  | WsAckFrame
  | WsConfirmFrame
  | WsActionFrame
  | WsCommandFrame
  | WsComponentSubmitFrame
  | WsRetryFrame
  | WsPingFrame;
export type Type12 = "message";
export type Text5 = string;
export type ThreadId10 = string | null;
export type Screen1 = string;
export type GoalId = string | null;
export type WorkflowId = string | null;
export type ExecutionId = string | null;
export type WorkspacePlaced = WsWorkspacePlaced[] | null;
export type Path1 = string;
export type Size = number;
export type Type13 = "ack";
export type Ids = string[];
export type Type14 = "confirm";
export type Id6 = string;
export type ThreadId11 = string;
export type Choice = "approve" | "deny";
export type Type15 = "action";
export type Payload = string;
export type ThreadId12 = string | null;
export type Type16 = "command";
export type ThreadId13 = string | null;
export type Name3 = "cancel" | "costs" | "status" | "onboarding" | "reset" | "reset_preview";
export type Type17 = "component_submit";
export type StepId = string;
export type SessionId1 = string | null;
export type ThreadId14 = string | null;
export type Type18 = "retry";
export type MessageId3 = string;
export type ThreadId15 = string;
export type Type19 = "ping";

export interface WsProtocol {
  inbound?: WsInboundFrame;
  outbound?: WsOutboundFrame;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsMessageFrame".
 */
export interface WsMessageFrame {
  type: Type;
  message: MessageSchema;
  onboarding?: OnboardingMeta | null;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "MessageSchema".
 */
export interface MessageSchema {
  id: Id;
  role: Role;
  text: Text;
  components: Components;
  read: Read;
  thread_id: ThreadId;
  created_at: CreatedAt;
  replaces?: Replaces;
  replaced_by?: ReplacedBy;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "OnboardingMeta".
 */
export interface OnboardingMeta {
  session_id: SessionId;
  completed: Completed;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsEditFrame".
 */
export interface WsEditFrame {
  type: Type1;
  id: Id1;
  thread_id?: ThreadId1;
  text?: Text1;
  components?: Components1;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsConfirmRequestFrame".
 */
export interface WsConfirmRequestFrame {
  type: Type2;
  id: Id2;
  thread_id?: ThreadId2;
  kind: Kind;
  round?: Round;
  title: Title;
  items: Items;
  source?: WsConfirmSource | null;
  expires_at?: ExpiresAt;
  actions: Actions;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsConfirmItem".
 */
export interface WsConfirmItem {
  item_id: ItemId;
  agent: Agent;
  tool?: Tool;
  effect_phrase: EffectPhrase;
  summary: Summary;
  conflict?: Conflict;
  editable_field?: EditableField;
  proposed_text?: ProposedText;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsConfirmSource".
 */
export interface WsConfirmSource {
  kind: Kind1;
  name: Name;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsConfirmAction".
 */
export interface WsConfirmAction {
  label: Label;
  value: Value;
  style?: Style;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsConfirmCancelFrame".
 */
export interface WsConfirmCancelFrame {
  type: Type3;
  id: Id3;
  thread_id?: ThreadId3;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsTypingFrame".
 */
export interface WsTypingFrame {
  type: Type4;
  thread_id?: ThreadId4;
  text?: Text2;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsTokenFrame".
 */
export interface WsTokenFrame {
  type: Type5;
  thread_id?: ThreadId5;
  text: Text3;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsErrorFrame".
 */
export interface WsErrorFrame {
  type: Type6;
  thread_id?: ThreadId6;
  detail: Detail;
  code?: Code;
  message_id?: MessageId;
  reason_code?: ReasonCode;
  reason_text?: ReasonText;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsMessageSupersededFrame".
 */
export interface WsMessageSupersededFrame {
  type: Type7;
  thread_id?: ThreadId7;
  message_id: MessageId1;
  replaced_by: ReplacedBy1;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsRefreshFrame".
 */
export interface WsRefreshFrame {
  type: Type8;
  thread_id?: ThreadId8;
  screen: Screen;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsPongFrame".
 */
export interface WsPongFrame {
  type: Type9;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsTraceUpdateFrame".
 */
export interface WsTraceUpdateFrame {
  type: Type10;
  thread_id: ThreadId9;
  message_id: MessageId2;
  partial?: Partial;
  agent: Agent1;
  routing_method: RoutingMethod;
  confidence: Confidence;
  score_gap: ScoreGap;
  is_compound: IsCompound;
  subtasks: Subtasks;
  memory_chunks: MemoryChunks;
  tool_calls: ToolCalls;
  total_duration_ms: TotalDurationMs;
  skills_used?: SkillsUsed;
  workspace?: WorkspaceUsageTraceResponse | null;
  procedure?: ProcedureUsageTraceResponse | null;
  conductor_hint?: ConductorHint;
  conductor_ledger?: ConductorLedger;
  judgments?: Judgments;
  sources?: Sources;
  effects_known?: EffectsKnown;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "MemoryChunkTraceResponse".
 */
export interface MemoryChunkTraceResponse {
  text: Text4;
  score: Score;
  source: Source;
  extraction_confidence?: ExtractionConfidence;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "ToolCallTraceResponse".
 */
export interface ToolCallTraceResponse {
  name: Name1;
  result_snippet: ResultSnippet;
  duration_ms: DurationMs;
  success: Success;
  access?: Access;
  reversibility?: Reversibility;
  undo_tool?: UndoTool;
  gate?: Gate;
  effect_phrase?: EffectPhrase1;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "SkillUsageTraceResponse".
 */
export interface SkillUsageTraceResponse {
  skill_id: SkillId;
  name: Name2;
  source: Source1;
  trigger: Trigger;
  similarity?: Similarity;
  script_ran?: ScriptRan;
  below_floor?: BelowFloor;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WorkspaceUsageTraceResponse".
 */
export interface WorkspaceUsageTraceResponse {
  runs?: Runs;
  files?: Files;
  script_ran?: ScriptRan1;
  unavailable?: Unavailable;
  planned?: Planned;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WorkspaceRunTraceResponse".
 */
export interface WorkspaceRunTraceResponse {
  command: Command;
  success: Success1;
  status?: Status;
  id?: Id4;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WorkspaceFileTraceResponse".
 */
export interface WorkspaceFileTraceResponse {
  path: Path;
  op: Op;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "ProcedureUsageTraceResponse".
 */
export interface ProcedureUsageTraceResponse {
  invocation_id: InvocationId;
  procedure_id: ProcedureId;
  version_id: VersionId;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "ConductorLedgerEntryResponse".
 */
export interface ConductorLedgerEntryResponse {
  agent: Agent2;
  status: Status1;
  request_id?: RequestId;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "JudgmentTraceResponse".
 */
export interface JudgmentTraceResponse {
  question_id: QuestionId;
  kind: Kind2;
  latency_ms: LatencyMs;
  answer?: Answer;
  probabilities?: Probabilities;
  peakedness?: Peakedness;
  model?: Model;
  input_tokens?: InputTokens;
  consumed?: Consumed;
  skip_reason?: SkipReason;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "SourceTraceResponse".
 */
export interface SourceTraceResponse {
  url: Url;
  title?: Title1;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsNotificationFrame".
 */
export interface WsNotificationFrame {
  type: Type11;
  id: Id5;
  event_type: EventType;
  source: Source2;
  title: Title2;
  body: Body;
  target_type: TargetType;
  target_id: TargetId;
  created_at: CreatedAt1;
  read?: Read1;
  push_class: PushClass;
  delivery: Delivery;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsSendMessageFrame".
 */
export interface WsSendMessageFrame {
  type: Type12;
  text: Text5;
  thread_id?: ThreadId10;
  context?: WsScreenContext | null;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsScreenContext".
 */
export interface WsScreenContext {
  screen: Screen1;
  goal_id?: GoalId;
  workflow_id?: WorkflowId;
  execution_id?: ExecutionId;
  workspace_placed?: WorkspacePlaced;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsWorkspacePlaced".
 */
export interface WsWorkspacePlaced {
  path: Path1;
  size: Size;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsAckFrame".
 */
export interface WsAckFrame {
  type: Type13;
  ids: Ids;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsConfirmFrame".
 */
export interface WsConfirmFrame {
  type: Type14;
  id: Id6;
  thread_id: ThreadId11;
  choice: Choice;
  edits?: Edits;
}
export interface Edits {
  [k: string]: string;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsActionFrame".
 */
export interface WsActionFrame {
  type: Type15;
  payload: Payload;
  thread_id?: ThreadId12;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsCommandFrame".
 */
export interface WsCommandFrame {
  type: Type16;
  thread_id?: ThreadId13;
  name: Name3;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsComponentSubmitFrame".
 */
export interface WsComponentSubmitFrame {
  type: Type17;
  step_id: StepId;
  values: Values;
  session_id?: SessionId1;
  thread_id?: ThreadId14;
}
export interface Values {
  [k: string]: unknown;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsRetryFrame".
 */
export interface WsRetryFrame {
  type: Type18;
  message_id: MessageId3;
  thread_id: ThreadId15;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsPingFrame".
 */
export interface WsPingFrame {
  type: Type19;
}
