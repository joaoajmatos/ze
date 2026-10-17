import { useEffect, useId } from "react";
import { useScreenContextStore, type ScreenPublication } from "./store";

/**
 * Publish what this page or widget shows. Registered on mount, updated when the content changes,
 * removed on unmount. Pass refs with `as_of` (the record's `updated_at` as displayed) and `parent_id` where needed.
 */
export function useScreenPublisher(publication: ScreenPublication | null | undefined): void {
  const token = useId();
  const key = JSON.stringify(publication ?? null);

  useEffect(() => {
    const value = JSON.parse(key) as ScreenPublication | null;
    if (value) useScreenContextStore.getState().publish(token, value);
    else useScreenContextStore.getState().remove(token);
  }, [token, key]);

  useEffect(() => () => useScreenContextStore.getState().remove(token), [token]);
}
