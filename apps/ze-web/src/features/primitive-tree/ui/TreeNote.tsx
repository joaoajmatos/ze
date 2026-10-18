/** Stands where a tree cannot be drawn; the message text around it still renders. */
export function TreeNote({ status }: { status: "legacy-failed" | "invalid" }) {
  return (
    <p className="note" role="note">
      {status === "legacy-failed" ? "This older view can't be shown." : "This view can't be shown."}
    </p>
  );
}
