import { goalPath, workflowPath } from "@/shared/config/places";

/** Route for the record a claim card is about, or null when the web app has no page for it. */
export function claimHref(subject: string, refId: string): string | null {
  switch (subject) {
    case "goal":
      return goalPath(refId);
    case "workflow":
      return workflowPath(refId);
    case "loop":
      return "/";
    default:
      return null;
  }
}
