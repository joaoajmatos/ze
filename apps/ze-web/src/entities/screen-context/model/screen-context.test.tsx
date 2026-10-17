import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { screenSnapshot } from "./snapshot";
import { useScreenContextStore } from "./store";
import { useScreenPublisher } from "./useScreenPublisher";

const NOW = new Date("2026-10-17T14:02:11Z");

beforeEach(() => useScreenContextStore.getState().reset());

describe("useScreenPublisher", () => {
  it("registers on mount, updates on change and removes on unmount", () => {
    const { rerender, unmount } = renderHook(({ id }) => useScreenPublisher({ subject: [{ kind: "goal", id }] }), {
      initialProps: { id: "g1" },
    });
    expect(screenSnapshot("/doing/goals/g1", NOW).subject).toEqual([{ kind: "goal", id: "g1" }]);
    rerender({ id: "g2" });
    expect(screenSnapshot("/doing/goals/g2", NOW).subject).toEqual([{ kind: "goal", id: "g2" }]);
    unmount();
    expect(screenSnapshot("/doing", NOW).subject).toBeUndefined();
    expect(useScreenContextStore.getState().publications.size).toBe(0);
  });

  it("a null publication publishes nothing", () => {
    renderHook(() => useScreenPublisher(null));
    expect(useScreenContextStore.getState().publications.size).toBe(0);
  });

  it("does not republish when the content is deep-equal", () => {
    let renders = 0;
    const { rerender } = renderHook(() => {
      renders++;
      useScreenPublisher({ visible: [{ kind: "goal", id: "g1" }] });
    });
    const before = useScreenContextStore.getState().publications;
    rerender();
    expect(renders).toBe(2);
    expect(useScreenContextStore.getState().publications).toBe(before);
  });
});

describe("screenSnapshot", () => {
  it("keeps as_of and parent_id on refs and drops empty fields", () => {
    act(() =>
      useScreenContextStore.getState().publish("a", {
        subject: [{ kind: "workflow_execution", id: "e1", parent_id: "w1", as_of: "2026-10-16T09:01:12Z", label: "Run" }],
      }),
    );
    const ctx = screenSnapshot("/doing/workflows/w1", NOW);
    expect(ctx.subject).toEqual([{ kind: "workflow_execution", id: "e1", parent_id: "w1", as_of: "2026-10-16T09:01:12Z", label: "Run" }]);
    expect(ctx.selection).toBeUndefined();
    expect(ctx.canvas).toBeUndefined();
  });

  it("merges publications in mount order and applies the caps", () => {
    const refs = (p: string, n: number) => Array.from({ length: n }, (_, i) => ({ kind: "goal", id: `${p}${i}` }));
    act(() => {
      const s = useScreenContextStore.getState();
      s.publish("a", { subject: refs("a", 2), selection: refs("a", 15), visible: refs("a", 20) });
      s.publish("b", { subject: refs("b", 2), selection: refs("b", 15), visible: refs("b", 20) });
    });
    const ctx = screenSnapshot("/doing", NOW);
    expect(ctx.subject?.map((r) => r.id)).toEqual(["a0", "a1", "b0"]);
    expect(ctx.selection).toHaveLength(20);
    expect(ctx.visible).toHaveLength(30);
    expect(ctx.visible?.[0].id).toBe("a0");
  });

  it("truncates long strings", () => {
    act(() => useScreenContextStore.getState().publish("a", { subject: [{ kind: "goal", id: "g", label: "L".repeat(300), component: "c".repeat(90) }] }));
    const ref = screenSnapshot("/doing", NOW).subject![0];
    expect(ref.label).toHaveLength(120);
    expect(ref.component).toHaveLength(40);
  });

  it("sets the place from placeOf, the path without its query, and captured_at", () => {
    expect(screenSnapshot("/doing/workflows/w1", NOW)).toMatchObject({ place: "doing", route: "/doing/workflows/w1", captured_at: NOW.toISOString() });
    expect(screenSnapshot("/", NOW).place).toBe("world");
    expect(screenSnapshot("/design", NOW).place).toBeUndefined();
  });

  it("uses the last focused module published", () => {
    act(() => {
      useScreenContextStore.getState().publish("a", { focused_module: "Goals" });
      useScreenContextStore.getState().publish("b", { focused_module: "Workflows" });
    });
    expect(screenSnapshot("/doing", NOW).focused_module).toBe("Workflows");
  });
});
