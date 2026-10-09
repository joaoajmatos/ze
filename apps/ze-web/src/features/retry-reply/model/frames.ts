import { useFrame } from "@/shared/api";

// Interim shapes from specs/phases/165-response-feedback-retry/contracts/api.md.
// Drop this file once the regenerated WS types carry `message_superseded` and
// `error.code`.
export interface MessageSupersededFrame {
  type: "message_superseded";
  message_id: string;
  replaced_by: string;
  thread_id: string;
}

export interface RetryErrorFrame {
  type: "error";
  thread_id?: string | null;
  detail: string;
  code?: "retry_unavailable" | "retry_failed" | "busy" | null;
  reason_code?: string | null;
  reason_text?: string | null;
}

export interface RetryOutboundFrame {
  type: "retry";
  message_id: string;
  thread_id: string;
}

export const useRetryFrame = useFrame as unknown as <T>(
  type: string,
  handler: (frame: T) => void,
) => void;
