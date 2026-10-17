import type { KeyboardEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Concern } from "@/shared/lib";

export interface Move {
  item: Concern;
  anchor: Concern;
  relation: "above" | "below";
}

const DRAG_THRESHOLD = 6;

interface Held {
  key: string;
  target: string | null;
  mode: "key" | "pointer";
}

/**
 * Reorder the ranked concerns by keyboard (Space lifts, arrows move the drop point, Space drops,
 * Escape cancels) or by dragging one mark onto another. Reminders have no rank and cannot move.
 */
export function useReorder(concerns: Concern[], onDrop: (move: Move) => void) {
  const ranked = useMemo(() => concerns.filter((c) => c.rank != null && c.kind !== "reminder").sort((a, b) => a.rank! - b.rank!), [concerns]);
  const [held, setHeld] = useState<Held | null>(null);
  const [announcement, setAnnouncement] = useState("");
  // Mirrors for the document listeners, which outlive a render.
  const heldRef = useRef<Held | null>(null);
  const pressRef = useRef<{ key: string; x: number; y: number } | null>(null);
  const suppressClick = useRef(false);
  const rankedRef = useRef(ranked);
  const onDropRef = useRef(onDrop);
  useEffect(() => {
    rankedRef.current = ranked;
    onDropRef.current = onDrop;
  });

  const set = useCallback((next: Held | null) => {
    heldRef.current = next;
    setHeld(next);
  }, []);

  const finish = useCallback(
    (h: Held | null) => {
      pressRef.current = null;
      const list = rankedRef.current;
      const item = list.find((c) => c.key === h?.key);
      const anchor = list.find((c) => c.key === h?.target);
      if (item && anchor && item.key !== anchor.key) {
        const relation = list.indexOf(anchor) < list.indexOf(item) ? "above" : "below";
        onDropRef.current({ item, anchor, relation });
        setAnnouncement(`Moved ${item.title} ${relation} ${anchor.title}.`);
      }
      set(null);
    },
    [set],
  );

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const p = pressRef.current;
      if (!p || heldRef.current) return;
      if (Math.hypot(e.clientX - p.x, e.clientY - p.y) > DRAG_THRESHOLD) set({ key: p.key, target: null, mode: "pointer" });
    };
    const onUp = () => {
      const h = heldRef.current;
      pressRef.current = null;
      if (h?.mode !== "pointer") return;
      suppressClick.current = true;
      setTimeout(() => (suppressClick.current = false), 0);
      finish(h);
    };
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
    return () => {
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
    };
  }, [finish, set]);

  const markProps = (key: string) => ({
    onKeyDown: (e: KeyboardEvent) => {
      const list = rankedRef.current;
      const h = heldRef.current;
      if (e.key === " ") {
        e.preventDefault();
        if (!h) {
          const item = list.find((c) => c.key === key);
          if (!item) return;
          set({ key, target: key, mode: "key" });
          setAnnouncement(`Lifted ${item.title}. Arrow keys move it, Space drops it, Escape cancels.`);
        } else if (h.mode === "key") finish(h);
        return;
      }
      if (!h || h.mode !== "key") return;
      if (e.key === "Escape") {
        e.preventDefault();
        set(null);
        setAnnouncement("Move cancelled.");
        return;
      }
      const back = e.key === "ArrowUp" || e.key === "ArrowLeft";
      const forward = e.key === "ArrowDown" || e.key === "ArrowRight";
      if (!back && !forward) return;
      e.preventDefault();
      const at = list.findIndex((c) => c.key === (h.target ?? h.key));
      const next = list[Math.min(list.length - 1, Math.max(0, at + (back ? -1 : 1)))];
      const mover = list.find((c) => c.key === h.key);
      if (!next || !mover) return;
      set({ ...h, target: next.key });
      const rel = list.indexOf(next) < list.indexOf(mover) ? "above" : "below";
      setAnnouncement(next.key === mover.key ? `${mover.title} stays where it is.` : `${mover.title} would go ${rel} ${next.title}. Space to drop.`);
    },
    onPointerDown: (e: { button: number; clientX: number; clientY: number }) => {
      if (e.button !== 0 || !rankedRef.current.some((c) => c.key === key)) return;
      pressRef.current = { key, x: e.clientX, y: e.clientY };
    },
    onPointerEnter: () => {
      const h = heldRef.current;
      if (h?.mode === "pointer" && h.key !== key && rankedRef.current.some((c) => c.key === key)) set({ ...h, target: key });
    },
  });

  return {
    lifted: held?.key ?? null,
    target: held?.target ?? null,
    announcement,
    markProps,
    /** True once right after a drag ends, so the click that follows does not select. */
    consumeClick: () => {
      const was = suppressClick.current;
      suppressClick.current = false;
      return was;
    },
    cancel: () => set(null),
  };
}

export type Reorder = ReturnType<typeof useReorder>;
