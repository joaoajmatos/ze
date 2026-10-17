import { beforeEach, describe, expect, it } from "vitest";
import { askAbout, useAskOverlay } from "./ask-overlay";

const route = { screen: "doing.workflows", workflow_id: "w1" };

beforeEach(() => useAskOverlay.getState().reset());

describe("ask overlay store", () => {
  it("submit opens the overlay and queues text with the route context", () => {
    expect(useAskOverlay.getState().submit("why?", route)).toBe(true);
    const s = useAskOverlay.getState();
    expect(s.open).toBe(true);
    expect(s.outbox).toMatchObject({ text: "why?", context: route });
  });

  it("refuses a second submit while an item is queued", () => {
    const { submit } = useAskOverlay.getState();
    submit("one", route);
    expect(submit("two", route)).toBe(false);
    expect(useAskOverlay.getState().outbox?.text).toBe("one");
  });

  it("ack clears the item and the explicit context", () => {
    askAbout({ text: "t", context: { screen: "doing.workflows", execution_id: "e1" } });
    useAskOverlay.getState().submit("go", route);
    const id = useAskOverlay.getState().outbox!.id;
    useAskOverlay.getState().ack(id);
    const s = useAskOverlay.getState();
    expect(s.outbox).toBeNull();
    expect(s.explicitContext).toBeNull();
    expect(s.open).toBe(true);
  });

  it("ack of an old id leaves a newer item alone", () => {
    useAskOverlay.getState().submit("one", route);
    const first = useAskOverlay.getState().outbox!.id;
    useAskOverlay.getState().ack(first);
    useAskOverlay.getState().submit("two", route);
    useAskOverlay.getState().ack(first);
    expect(useAskOverlay.getState().outbox?.text).toBe("two");
  });

  it("askAbout opens prefilled and queues nothing", () => {
    askAbout({ text: "Why did this run fail?", context: { screen: "doing.workflows", workflow_id: "w1", execution_id: "e1" } });
    const s = useAskOverlay.getState();
    expect(s.open).toBe(true);
    expect(s.draft).toBe("Why did this run fail?");
    expect(s.outbox).toBeNull();
  });

  it("a submit after askAbout merges the explicit context over the route one", () => {
    askAbout({ text: "x", context: { screen: "doing.workflows", workflow_id: "w1", execution_id: "e1" } });
    useAskOverlay.getState().submit("x", { screen: "doing.goals", goal_id: "g9" });
    expect(useAskOverlay.getState().outbox?.context).toEqual({
      screen: "doing.workflows",
      goal_id: "g9",
      workflow_id: "w1",
      execution_id: "e1",
    });
  });

  it("askAbout without text keeps what the person already typed, and asks for focus", () => {
    useAskOverlay.getState().setDraft("half a thought");
    const before = useAskOverlay.getState().focusTick;
    askAbout({ context: { screen: "mind" } });
    expect(useAskOverlay.getState().draft).toBe("half a thought");
    expect(useAskOverlay.getState().focusTick).toBe(before + 1);
  });

  it("an accepted submit clears the draft; a refused one keeps it", () => {
    const { submit, setDraft } = useAskOverlay.getState();
    setDraft("one");
    submit("one", route);
    expect(useAskOverlay.getState().draft).toBe("");
    setDraft("two");
    expect(submit("two", route)).toBe(false);
    expect(useAskOverlay.getState().draft).toBe("two");
  });

  it("close drops the queue and explicit context but not the typed draft", () => {
    askAbout({ text: "x", context: { screen: "mind" } });
    useAskOverlay.getState().submit("y", route);
    useAskOverlay.getState().setDraft("keep me");
    useAskOverlay.getState().close();
    const s = useAskOverlay.getState();
    expect(s).toMatchObject({ open: false, outbox: null, explicitContext: null, draft: "keep me" });
  });
});
