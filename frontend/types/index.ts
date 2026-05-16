export type UiState =
  | "idle"
  | "streaming"
  | "awaiting_confirmation"
  | "draft_review"
  | "reconnecting"
  | "disconnected"
  | "error"

export interface AgentMeta {
  agent: string
  routingMethod: "embedding" | "haiku"
  confidence: number | null
}

export interface ZeMessage {
  id: string
  role: "user" | "agent" | "system"
  content: string
  isStreaming: boolean
  meta?: AgentMeta
}

export interface ConfirmationRequest {
  type: "confirmation_request"
  draft: string
  agent: string
  action: string
}

export type WsServerMessage =
  | { type: "token"; content: string }
  | { type: "done"; agent: string; routing_method: string; confidence: number | null }
  | { type: "confirmation_request"; draft: string; agent: string; action: string }
  | { type: "confirmation_expired" }
  | { type: "error"; message: string }
