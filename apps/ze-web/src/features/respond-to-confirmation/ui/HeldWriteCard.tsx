import type { HeldWriteOut } from "@myguyze/ze-client";
import { useDecideHeldWriteMutation } from "@/entities/confirmation";
import { ConfirmationCard } from "./ConfirmationCard";

const HELD_ACTIONS = [
  { label: "Approve all", value: "approve", style: "primary" as const },
  { label: "Deny all", value: "deny", style: "secondary" as const },
];

interface HeldWriteCardProps {
  held: HeldWriteOut;
  disabled?: boolean;
  highlighted?: boolean;
}

/**
 * One held write waiting for the user. It owns the decision: Approve and Deny call the held-write
 * mutation with the request id, edits included, and the card is disabled while that request is pending.
 * A write with an editable field opens the full confirmation card; any other shows the effect and two actions.
 */
export function HeldWriteCard({ held, disabled = false, highlighted = false }: HeldWriteCardProps) {
  const decide = useDecideHeldWriteMutation();
  const pending = decide.isPending && decide.variables?.requestId === held.request_id;
  const off = disabled || pending;

  function answer(value: string, edits: Record<string, string>) {
    decide.mutate({ requestId: held.request_id, choice: value === "approve" ? "approve" : "deny", edits });
  }

  const editable = held.items.some((i) => i.editable_field);
  return (
    <div data-testid={`held-write-${held.request_id}`} data-highlighted={highlighted ? "true" : undefined} className={`held-write ${highlighted ? "focused" : ""}`}>
      {editable ? (
        <ConfirmationCard
          title="Waiting for your OK"
          items={held.items}
          source={{ kind: held.source, name: held.source_name }}
          actions={HELD_ACTIONS}
          disabled={off}
          highlighted={highlighted}
          onRespond={answer}
        />
      ) : (
        <>
          <p className="t">{held.source_name}</p>
          {held.items.map((item) => (
            <p key={item.item_id} className="s">
              <span className="key">{item.effect_phrase}</span>
              {item.summary ? ` · ${item.summary}` : ""}
            </p>
          ))}
          <span className="acts">
            <button type="button" className="ctl" disabled={off} onClick={() => answer("approve", {})}>
              Approve
            </button>
            <button type="button" className="ctl" disabled={off} onClick={() => answer("deny", {})}>
              Deny
            </button>
          </span>
        </>
      )}
      {decide.isError && (
        <p className="hot" role="alert">
          That didn't go through. Try again.
        </p>
      )}
    </div>
  );
}
