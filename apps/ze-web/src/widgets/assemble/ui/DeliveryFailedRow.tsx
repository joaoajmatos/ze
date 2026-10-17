import { resendTurn } from "@/features/turn-stream";
import { Control } from "@/shared/ui";

/** The turn ended with no reply. Resend replays the last message with what it was sent with. */
export function DeliveryFailedRow({ threadId }: { threadId: string }) {
  return (
    <div className="assemble-failed" role="alert">
      <span className="lbl hot">Ze did not answer</span>
      <Control onClick={() => resendTurn(threadId)}>Resend</Control>
    </div>
  );
}
