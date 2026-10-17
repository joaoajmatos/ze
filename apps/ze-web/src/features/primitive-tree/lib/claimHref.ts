/** Route for the record a claim card is about, or null when the web app has no page for it. */
export function claimHref(subject: string, refId: string): string | null {
  switch (subject) {
    case "goal":
      return `/goals/${refId}`;
    case "workflow":
      return `/workflows/${refId}`;
    case "loop":
      return "/loops";
    default:
      return null;
  }
}
