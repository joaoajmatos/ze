import { takeOver, useConnectionState } from "@/shared/api";
import { Control } from "@/shared/ui";

export const DISPLACED_LINE = "Ze is open in another window";

/** Another window holds the connection. Shown on every place until this window takes it back. */
export function DisplacedNotice() {
  if (useConnectionState() !== "displaced") return null;
  return (
    <div className="displaced-notice" role="status">
      <span className="lbl">{DISPLACED_LINE}</span>
      <Control onClick={takeOver}>Use here</Control>
    </div>
  );
}
