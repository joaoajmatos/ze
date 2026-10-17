import type { HeldWriteOut, LoopListItem } from "@myguyze/ze-client";
import type { PendingConfirm } from "@/features/respond-to-confirmation";

export type Decision =
  | { kind: "held_write"; id: string; title: string; at: Date | null; expiresAt: Date | null; held: HeldWriteOut }
  | { kind: "gate"; id: string; goalId: string; title: string; goalTitle: string; at: Date | null; expiresAt: null }
  | { kind: "suspected_loop"; id: string; title: string; at: Date | null; expiresAt: null; loop: LoopListItem }
  | { kind: "chat_confirmation"; id: string; threadId: string; title: string; at: Date | null; expiresAt: Date | null; pending: PendingConfirm };
