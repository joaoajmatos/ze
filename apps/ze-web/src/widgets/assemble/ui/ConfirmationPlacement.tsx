import { ConfirmationCard, useConfirmation } from "@/features/respond-to-confirmation";

/** The thread's open confirmations, in place after the latest exchange. Held writes show on every thread. */
export function ConfirmationPlacement({ threadId }: { threadId: string }) {
  const { pendingConfirms, respond } = useConfirmation(false, threadId);
  if (pendingConfirms.length === 0) return null;
  return (
    <div className="assemble-confirmations">
      {pendingConfirms.map((pending) => (
        <ConfirmationCard
          key={pending.id}
          title={pending.title}
          items={pending.items}
          source={pending.source}
          actions={pending.actions}
          disabled={pending.submitted}
          onRespond={(value, edits) => respond(pending.id, value, edits)}
        />
      ))}
    </div>
  );
}
