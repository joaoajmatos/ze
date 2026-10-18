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
  | WsMessageRollbackFrame
  | WsRefreshFrame
  | WsPongFrame
  | WsTraceUpdateFrame
  | WsNotificationFrame
  | WsUiActionResultFrame;
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
export type State = "partial" | "rolled_back_awaiting_confirmation" | "rolled_back_retry_failed" | "superseded";
export type EntryId = string;
export type Tool = string;
export type EffectPhrase = string;
export type Outcome = "undone" | "failed" | "not_attempted";
export type At = string | null;
export type FailureCode = string | null;
export type Entries = RollbackEntryResponse[];
export type ReplacedBy1 = string | null;
export type SessionId = string;
export type Completed = boolean;
export type UiVersion = string | null;
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
export type Kind = "write" | "budget" | "held" | "prompt";
export type Round = number;
export type Title = string;
export type ItemId = string;
export type Agent = string;
export type Tool1 = string | null;
export type EffectPhrase1 = string;
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
export type Reason = "answered" | null;
export type Type4 = "typing";
export type ThreadId4 = string | null;
export type Text2 = string | null;
export type Type5 = "token";
export type ThreadId5 = string | null;
export type Text3 = string;
export type Type6 = "error";
export type ThreadId6 = string | null;
export type Detail = string;
export type Code = ("busy" | "retry_unavailable" | "retry_failed" | "retry_partial") | null;
export type MessageId = string | null;
export type ReasonCode = string | null;
export type ReasonText = string | null;
export type RolledBack = boolean | null;
export type Plan = UndoPlanEntryResponse[] | null;
export type EntryId1 = string;
export type Tool2 = string;
export type EffectPhrase2 = string;
export type UndoNote = string | null;
export type Type7 = "message_superseded";
export type ThreadId7 = string | null;
export type MessageId1 = string;
export type ReplacedBy2 = string;
export type Type8 = "message_rollback";
export type ThreadId8 = string | null;
export type MessageId2 = string;
export type Type9 = "refresh";
export type ThreadId9 = string | null;
export type Screen = string;
export type Type10 = "pong";
export type Type11 = "trace_update";
export type ThreadId10 = string;
export type MessageId3 = string;
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
export type Access = "read" | "write" | "delegate" | "script" | "unknown";
export type Reversibility = ("reversible" | "irreversible") | null;
export type UndoTool = string | null;
export type Gate =
  | "none"
  | "approved"
  | "pre_approved"
  | "parked"
  | "denied"
  | "refused"
  | "refused_over_cap"
  | "expired"
  | "duplicate";
export type EffectPhrase3 = string | null;
export type Agent2 = string | null;
export type CallIndex = number;
export type CallId = string;
export type StartOffsetMs = number | null;
export type ParentCallId = string | null;
export type Source1 = string;
export type SourceCut = boolean;
export type Outcome1 = string;
export type Limit = ("wall_time" | "inner_calls" | "spend" | "result_size") | null;
export type SourceHash = string;
export type ProcedureId = string | null;
export type ToolCalls = ToolCallTraceResponse[];
export type ToolDurationMs = number;
export type SkillId = string;
export type Name2 = string;
export type Source2 = string;
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
export type ProcedureId1 = string;
export type VersionId = string;
export type ConductorHint =
  | {
      [k: string]: string;
    }[]
  | null;
export type Agent3 = string;
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
export type Surface = string | null;
export type Name3 = string;
export type Value1 = number;
export type Judgments = JudgmentTraceResponse[];
export type Url = string;
export type Title1 = string;
export type Sources = SourceTraceResponse[];
export type EffectsKnown = boolean;
export type RequestId1 = string;
export type Round1 = number;
export type ItemId1 = string;
export type Agent4 = string;
export type Tool3 = string | null;
export type Effect = string | null;
export type Summary1 = string;
export type Outcome2 = "approved" | "edited" | "pre_approved" | "denied" | "timed_out" | "superseded" | "refused";
export type WriteConfirmations = WriteConfirmationOutcomeResponse[];
export type Replaces1 = string;
export type Entries1 = RollbackEntryResponse[];
export type Agent5 = string;
export type Tier = "simple" | "full";
export type DecidedBy = string;
export type Model1 = string;
export type Origin = "ask_bar" | "chat_about" | "preset";
export type Place = string | null;
export type Route = string | null;
export type Subject = string[];
export type SelectionCount = number;
export type VisibleCount = number;
export type CanvasCount = number;
export type FocusedModule = string | null;
export type CapturedAt = string | null;
export type NoteChars = number;
export type Invalid = string[];
export type Kind3 = string;
export type Id5 = string;
export type Status2 = "ok" | "missing" | "changed" | "failed" | "timeout" | "cut";
export type Ms = number;
export type Resolvers = ScreenResolverTraceResponse[];
export type Modality = "voice";
export type DurationS = number | null;
export type Edited = boolean | null;
export type SpanStart = number;
export type SpanEnd = number;
export type ResumeRecapApplied = boolean;
export type TurnDurationMs = number | null;
export type PausedMs = number;
export type Name4 = string;
export type StartMs = number;
export type DurationMs1 = number;
export type Run = number;
export type Stages = StageTimingResponse[];
export type MainModel = string | null;
export type Model2 = string;
export type Calls = number;
export type PromptTokens = number;
export type CompletionTokens = number;
export type MaxPromptTokens = number;
export type CostUsd = number;
export type Estimated = boolean;
export type Models = ModelUsageResponse[];
export type ContextFill = number | null;
export type ContextWindow = number | null;
export type Estimated1 = boolean;
export type SystemOneTokens = number;
export type Agent6 = string;
export type Score1 = number;
export type RoutingScores = RoutingScoreResponse[];
export type Threshold = number;
export type Gap = number;
export type TelemetryPartial = boolean;
export type Type12 = "notification";
export type Id6 = string;
export type EventType = string;
export type Source3 = string;
export type Title2 = string;
export type Body = string;
export type TargetType = string | null;
export type TargetId = string | null;
export type TargetParentId = string | null;
export type CreatedAt1 = string;
export type Read1 = boolean;
export type PushClass = "requested" | "accountability" | "discretionary";
export type Urgency = "low" | "normal" | "high";
export type Delivery = "delivered" | "held" | "released" | "suppressed" | "failed";
export type Type13 = "ui_action_result";
export type Id7 = string;
export type ThreadId11 = string | null;
export type Ok = boolean;
export type Line = string;
export type Code1 = "busy" | null;
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsOutboundFrame".
 */
export type WsOutboundFrame =
  | WsSendMessageFrame
  | WsAckFrame
  | WsConfirmFrame
  | WsActionFrame
  | WsUiActionFrame
  | WsCommandFrame
  | WsComponentSubmitFrame
  | WsRetryFrame
  | WsPingFrame;
export type Type14 = "message";
export type Text5 = string;
export type ThreadId12 = string | null;
export type Place1 = ("world" | "ask" | "doing" | "mind" | "governance" | "plugin") | null;
export type Route1 = string | null;
export type Origin1 = ("ask_bar" | "chat_about" | "preset") | null;
export type Subject1 = WsScreenRef[] | null;
export type Kind4 = string;
export type Id8 = string;
export type Label1 = string | null;
export type Component = string | null;
export type ParentId = string | null;
export type AsOf = string | null;
export type Selection = WsScreenRef[] | null;
export type Visible = WsScreenRef[] | null;
export type FocusedModule1 = string | null;
export type Canvas = WsCanvasRef[] | null;
export type Index = number;
export type Type15 = string;
export type CapturedAt1 = string | null;
export type WorkspacePlaced = WsWorkspacePlaced[] | null;
export type Path1 = string;
export type Size = number;
export type Compose = ("slipping" | "decisions" | "topic") | null;
export type Topic = string | null;
export type TranscriptionId = string;
export type Type16 = "ack";
export type Ids = string[];
export type Type17 = "confirm";
export type Id9 = string;
export type ThreadId13 = string;
export type Choice = "approve" | "deny";
export type Type18 = "action";
export type Payload = string;
export type ThreadId14 = string | null;
export type Type19 = "ui_action";
export type Id10 = string;
export type ThreadId15 = string;
export type Kind5 = "tool";
export type Owner = string;
export type Tool4 = string;
export type Type20 = "command";
export type ThreadId16 = string | null;
export type Name5 = "cancel" | "costs" | "status" | "onboarding";
export type Type21 = "component_submit";
export type StepId = string;
export type SessionId1 = string | null;
export type ThreadId17 = string | null;
export type Type22 = "retry";
export type MessageId4 = string;
export type ThreadId18 = string;
export type ConfirmedPlan = string[] | null;
export type Type23 = "ping";

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
  ui_version?: UiVersion;
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
  rollback?: RollbackRecordResponse | null;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "RollbackRecordResponse".
 */
export interface RollbackRecordResponse {
  state: State;
  entries?: Entries;
  replaced_by?: ReplacedBy1;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "RollbackEntryResponse".
 */
export interface RollbackEntryResponse {
  entry_id: EntryId;
  tool: Tool;
  effect_phrase: EffectPhrase;
  outcome: Outcome;
  at?: At;
  failure_code?: FailureCode;
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
  tool?: Tool1;
  effect_phrase: EffectPhrase1;
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
  reason?: Reason;
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
  rolled_back?: RolledBack;
  rollback?: RollbackRecordResponse | null;
  plan?: Plan;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "UndoPlanEntryResponse".
 */
export interface UndoPlanEntryResponse {
  entry_id: EntryId1;
  tool: Tool2;
  effect_phrase: EffectPhrase2;
  undo_note?: UndoNote;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsMessageSupersededFrame".
 */
export interface WsMessageSupersededFrame {
  type: Type7;
  thread_id?: ThreadId7;
  message_id: MessageId1;
  replaced_by: ReplacedBy2;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsMessageRollbackFrame".
 */
export interface WsMessageRollbackFrame {
  type: Type8;
  thread_id?: ThreadId8;
  message_id: MessageId2;
  rollback: RollbackRecordResponse;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsRefreshFrame".
 */
export interface WsRefreshFrame {
  type: Type9;
  thread_id?: ThreadId9;
  screen: Screen;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsPongFrame".
 */
export interface WsPongFrame {
  type: Type10;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsTraceUpdateFrame".
 */
export interface WsTraceUpdateFrame {
  type: Type11;
  thread_id: ThreadId10;
  message_id: MessageId3;
  partial?: Partial;
  agent: Agent1;
  routing_method: RoutingMethod;
  confidence: Confidence;
  score_gap: ScoreGap;
  is_compound: IsCompound;
  subtasks: Subtasks;
  memory_chunks: MemoryChunks;
  tool_calls: ToolCalls;
  tool_duration_ms: ToolDurationMs;
  skills_used?: SkillsUsed;
  workspace?: WorkspaceUsageTraceResponse | null;
  procedure?: ProcedureUsageTraceResponse | null;
  conductor_hint?: ConductorHint;
  conductor_ledger?: ConductorLedger;
  judgments?: Judgments;
  sources?: Sources;
  effects_known?: EffectsKnown;
  write_confirmations?: WriteConfirmations;
  rollback?: RollbackTraceResponse | null;
  tier?: TierTraceResponse | null;
  screen?: ScreenTraceResponse | null;
  input?: InputTraceResponse | null;
  compaction?: CompactionTraceResponse | null;
  resume_recap_applied?: ResumeRecapApplied;
  turn_duration_ms?: TurnDurationMs;
  paused_ms?: PausedMs;
  stages?: Stages;
  usage?: TurnUsageResponse | null;
  routing_scores?: RoutingScores;
  routing_thresholds?: RoutingThresholdsResponse | null;
  telemetry_partial?: TelemetryPartial;
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
  effect_phrase?: EffectPhrase3;
  agent?: Agent2;
  call_index?: CallIndex;
  call_id?: CallId;
  start_offset_ms?: StartOffsetMs;
  parent_call_id?: ParentCallId;
  script?: ScriptTraceResponse | null;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "ScriptTraceResponse".
 */
export interface ScriptTraceResponse {
  source: Source1;
  source_cut: SourceCut;
  outcome: Outcome1;
  limit?: Limit;
  source_hash: SourceHash;
  procedure_id?: ProcedureId;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "SkillUsageTraceResponse".
 */
export interface SkillUsageTraceResponse {
  skill_id: SkillId;
  name: Name2;
  source: Source2;
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
  procedure_id: ProcedureId1;
  version_id: VersionId;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "ConductorLedgerEntryResponse".
 */
export interface ConductorLedgerEntryResponse {
  agent: Agent3;
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
  surface?: Surface;
  bar?: JudgmentBarResponse | null;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "JudgmentBarResponse".
 */
export interface JudgmentBarResponse {
  name: Name3;
  value: Value1;
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
 * via the `definition` "WriteConfirmationOutcomeResponse".
 */
export interface WriteConfirmationOutcomeResponse {
  request_id: RequestId1;
  round: Round1;
  item_id: ItemId1;
  agent: Agent4;
  tool?: Tool3;
  effect?: Effect;
  summary?: Summary1;
  outcome: Outcome2;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "RollbackTraceResponse".
 */
export interface RollbackTraceResponse {
  replaces: Replaces1;
  entries?: Entries1;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "TierTraceResponse".
 */
export interface TierTraceResponse {
  agent: Agent5;
  tier: Tier;
  decided_by: DecidedBy;
  model: Model1;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "ScreenTraceResponse".
 */
export interface ScreenTraceResponse {
  origin?: Origin;
  place?: Place;
  route?: Route;
  subject?: Subject;
  selection_count?: SelectionCount;
  visible_count?: VisibleCount;
  canvas_count?: CanvasCount;
  focused_module?: FocusedModule;
  captured_at?: CapturedAt;
  note_chars?: NoteChars;
  invalid?: Invalid;
  resolvers?: Resolvers;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "ScreenResolverTraceResponse".
 */
export interface ScreenResolverTraceResponse {
  kind: Kind3;
  id: Id5;
  status: Status2;
  ms?: Ms;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "InputTraceResponse".
 */
export interface InputTraceResponse {
  modality: Modality;
  duration_s?: DurationS;
  edited?: Edited;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "CompactionTraceResponse".
 */
export interface CompactionTraceResponse {
  span_start: SpanStart;
  span_end: SpanEnd;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "StageTimingResponse".
 */
export interface StageTimingResponse {
  name: Name4;
  start_ms: StartMs;
  duration_ms: DurationMs1;
  run?: Run;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "TurnUsageResponse".
 */
export interface TurnUsageResponse {
  main_model?: MainModel;
  models?: Models;
  context_fill?: ContextFill;
  context_window?: ContextWindow;
  estimated?: Estimated1;
  system_one_tokens?: SystemOneTokens;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "ModelUsageResponse".
 */
export interface ModelUsageResponse {
  model: Model2;
  calls: Calls;
  prompt_tokens: PromptTokens;
  completion_tokens: CompletionTokens;
  max_prompt_tokens: MaxPromptTokens;
  cost_usd: CostUsd;
  estimated?: Estimated;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "RoutingScoreResponse".
 */
export interface RoutingScoreResponse {
  agent: Agent6;
  score: Score1;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "RoutingThresholdsResponse".
 */
export interface RoutingThresholdsResponse {
  threshold: Threshold;
  gap: Gap;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsNotificationFrame".
 */
export interface WsNotificationFrame {
  type: Type12;
  id: Id6;
  event_type: EventType;
  source: Source3;
  title: Title2;
  body: Body;
  target_type: TargetType;
  target_id: TargetId;
  target_parent_id: TargetParentId;
  created_at: CreatedAt1;
  read?: Read1;
  push_class: PushClass;
  urgency: Urgency;
  delivery: Delivery;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsUiActionResultFrame".
 */
export interface WsUiActionResultFrame {
  type: Type13;
  id: Id7;
  thread_id?: ThreadId11;
  ok: Ok;
  line: Line;
  code?: Code1;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsSendMessageFrame".
 */
export interface WsSendMessageFrame {
  type: Type14;
  text: Text5;
  thread_id?: ThreadId12;
  context?: WsScreenContext | null;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsScreenContext".
 */
export interface WsScreenContext {
  place?: Place1;
  route?: Route1;
  origin?: Origin1;
  subject?: Subject1;
  selection?: Selection;
  visible?: Visible;
  focused_module?: FocusedModule1;
  canvas?: Canvas;
  captured_at?: CapturedAt1;
  workspace_placed?: WorkspacePlaced;
  compose?: Compose;
  topic?: Topic;
  voice?: WsVoiceRef | null;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsScreenRef".
 */
export interface WsScreenRef {
  kind: Kind4;
  id: Id8;
  label?: Label1;
  component?: Component;
  parent_id?: ParentId;
  as_of?: AsOf;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsCanvasRef".
 */
export interface WsCanvasRef {
  index: Index;
  type: Type15;
  ref?: WsScreenRef | null;
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
 * via the `definition` "WsVoiceRef".
 */
export interface WsVoiceRef {
  transcription_id: TranscriptionId;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsAckFrame".
 */
export interface WsAckFrame {
  type: Type16;
  ids: Ids;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsConfirmFrame".
 */
export interface WsConfirmFrame {
  type: Type17;
  id: Id9;
  thread_id: ThreadId13;
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
  type: Type18;
  payload: Payload;
  thread_id?: ThreadId14;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsUiActionFrame".
 */
export interface WsUiActionFrame {
  type: Type19;
  id: Id10;
  thread_id: ThreadId15;
  action: WsUiToolAction;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsUiToolAction".
 */
export interface WsUiToolAction {
  kind: Kind5;
  owner: Owner;
  tool: Tool4;
  args?: Args;
}
export interface Args {
  [k: string]: string | number | boolean;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsCommandFrame".
 */
export interface WsCommandFrame {
  type: Type20;
  thread_id?: ThreadId16;
  name: Name5;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsComponentSubmitFrame".
 */
export interface WsComponentSubmitFrame {
  type: Type21;
  step_id: StepId;
  values: Values;
  session_id?: SessionId1;
  thread_id?: ThreadId17;
}
export interface Values {
  [k: string]: unknown;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsRetryFrame".
 */
export interface WsRetryFrame {
  type: Type22;
  message_id: MessageId4;
  thread_id: ThreadId18;
  confirmed_plan?: ConfirmedPlan;
}
/**
 * This interface was referenced by `WsProtocol`'s JSON-Schema
 * via the `definition` "WsPingFrame".
 */
export interface WsPingFrame {
  type: Type23;
}
