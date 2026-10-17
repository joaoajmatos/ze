type Listener = () => void;

/** A controllable `matchMedia` for tests: set which queries match, then fire `change`. */
export function mockMatchMedia(initial: Record<string, boolean> = {}) {
  const matches: Record<string, boolean> = { ...initial };
  const listeners = new Map<string, Set<Listener>>();
  const original = window.matchMedia;

  window.matchMedia = ((query: string) => ({
    get matches() {
      return matches[query] ?? false;
    },
    media: query,
    onchange: null,
    addEventListener: (_: string, l: Listener) => {
      if (!listeners.has(query)) listeners.set(query, new Set());
      listeners.get(query)!.add(l);
    },
    removeEventListener: (_: string, l: Listener) => listeners.get(query)?.delete(l),
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;

  return {
    set(query: string, value: boolean) {
      matches[query] = value;
      listeners.get(query)?.forEach((l) => l());
    },
    listenerCount(query: string) {
      return listeners.get(query)?.size ?? 0;
    },
    restore() {
      window.matchMedia = original;
    },
  };
}
