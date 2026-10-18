import { Control, Dialog } from "@/shared/ui";
import type { WhyTarget } from "../lib/why";
import { TraceModule } from "./TraceModule";

/** The trace rail in a dialog: the overlay's "Why?" and the phone layout. Escape closes; focus returns to the opener. */
export function TraceSheet({ threadId, messageId, target, onClose }: { threadId: string; messageId: string | null; target: WhyTarget | null; onClose: () => void }) {
  return (
    <Dialog title="Why Ze said this" onClose={onClose}>
      <TraceModule threadId={threadId} messageId={messageId} openSection={target?.section ?? null} highlight={target?.highlight ?? []} />
      <Control onClick={onClose}>Close</Control>
    </Dialog>
  );
}
