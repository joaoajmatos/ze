import { useCallback, useState } from "react";

function readFlag(key: string): boolean {
  try {
    return localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

export function useOptionalCharts(storageKey: string) {
  const [visible, setVisible] = useState(() => readFlag(storageKey));

  const setChartsVisible = useCallback(
    (next: boolean) => {
      setVisible(next);
      try {
        localStorage.setItem(storageKey, next ? "1" : "0");
      } catch {
        /* ignore quota / private mode */
      }
    },
    [storageKey],
  );

  return { chartsVisible: visible, setChartsVisible };
}
