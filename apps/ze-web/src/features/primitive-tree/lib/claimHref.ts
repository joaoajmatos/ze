import { goalPath, workflowPath } from "@/shared/config/places";
import { focusHref } from "@/shared/lib/notification-href";

/** Route for the record a claim card is about, or null when the web app has no page for it. */
export function claimHref(subject: string, refId: string): string | null {
  switch (subject) {
    case "goal":
      return goalPath(refId);
    case "workflow":
      return workflowPath(refId);
    case "loop":
    case "hypothesis":
    case "held_write":
      return focusHref(subject, refId);
    default:
      return null;
  }
}
