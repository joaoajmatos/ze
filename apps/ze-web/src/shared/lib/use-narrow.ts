import { useMediaQuery } from "./use-media-query";

export const NARROW_QUERY = "(max-width: 1023px)";

/** Phone-width layout. */
export function useNarrow(): boolean {
  return useMediaQuery(NARROW_QUERY);
}
