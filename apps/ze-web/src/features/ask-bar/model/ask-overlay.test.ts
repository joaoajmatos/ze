import { beforeEach, describe, expect, it } from "vitest";
import { aboutContext, askAbout, useAskOverlay } from "./ask-overlay";

const route = { place: "doing" as const, route: "/doing/workflows/w1", captured_at: "2026-10-17T14:00:00Z" };
const workflow = { kind: "workflow", id: "w1", label: "Weekly report" };

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

  it("ack drops the item and keeps the explicit context until close", () => {
    askAbout({ text: "t", context: { subject: [workflow] } });
    useAskOverlay.getState().submit("go", route);
    const id = useAskOverlay.getState().outbox!.id;
    useAskOverlay.getState().ack(id);
    const s = useAskOverlay.getState();
    expect(s.outbox).toBeNull();
    expect(s.explicitContext).toEqual({ subject: [workflow] });
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
    askAbout({ text: "Why did this run fail?", context: { subject: [workflow] } });
    const s = useAskOverlay.getState();
    expect(s.open).toBe(true);
    expect(s.draft).toBe("Why did this run fail?");
    expect(s.outbox).toBeNull();
  });

  it("a submit after askAbout merges the explicit context over the route one", () => {
    askAbout({ text: "x", context: { subject: [workflow], origin: "chat_about" } });
    useAskOverlay.getState().submit("x", { ...route, place: "mind" });
    expect(useAskOverlay.getState().outbox?.context).toEqual({ ...route, place: "mind", subject: [workflow], origin: "chat_about" });
  });

  it("askAbout without text keeps what the person already typed, and asks for focus", () => {
    useAskOverlay.getState().setDraft("half a thought");
    const before = useAskOverlay.getState().focusTick;
    askAbout({ context: { place: "mind" } });
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

  it("close puts an unsent message back in the draft instead of losing it", () => {
    askAbout({ text: "x", context: { place: "mind" } });
    useAskOverlay.getState().submit("y", route);
    useAskOverlay.getState().setDraft("keep me");
    useAskOverlay.getState().close();
    const s = useAskOverlay.getState();
    expect(s).toMatchObject({ open: false, outbox: null, explicitContext: null, about: null, draft: "y keep me" });
  });
});

describe("chat about", () => {
  const about = { ref: workflow, origin: "chat_about" as const, suggestions: ["a", "b", "c"] };

  it("off Ask it opens the overlay with the subject as explicit context and asks for focus and a glance", () => {
    const element = document.createElement("div");
    useAskOverlay.getState().startAbout(about, { inPlace: false, element, glance: true });
    const s = useAskOverlay.getState();
    expect(s.open).toBe(true);
    expect(s.explicitContext).toEqual({ origin: "chat_about", subject: [workflow] });
    expect(s.about).toEqual(about);
    expect(s.focusTick).toBe(1);
    expect(s.glanceTick).toBe(1);
    expect(s.glanceTarget).toBe(element);
  });

  it("on Ask it sets the composer's subject without opening the overlay", () => {
    useAskOverlay.getState().startAbout(about, { inPlace: true, element: null, glance: true });
    const s = useAskOverlay.getState();
    expect(s.open).toBe(false);
    expect(s.explicitContext).toBeNull();
    expect(s.about).toEqual(about);
    expect(s.focusTick).toBe(1);
  });

  it("no glance is requested when told not to (reduced motion)", () => {
    useAskOverlay.getState().startAbout(about, { inPlace: false, element: document.body, glance: false });
    expect(useAskOverlay.getState().glanceTick).toBe(0);
  });

  it("the first message goes out as chat_about; the next as ask_bar with the same subject", () => {
    useAskOverlay.getState().startAbout(about, { inPlace: false, glance: false });
    useAskOverlay.getState().submit("first", route);
    expect(useAskOverlay.getState().outbox?.context).toMatchObject({ origin: "chat_about", subject: [workflow] });
    useAskOverlay.getState().ack(useAskOverlay.getState().outbox!.id);
    useAskOverlay.getState().submit("second", route);
    expect(useAskOverlay.getState().outbox?.context).toMatchObject({ origin: "ask_bar", subject: [workflow] });
  });

  it("aboutSent reverts the origin on the Ask composer's subject", () => {
    useAskOverlay.getState().startAbout(about, { inPlace: true, glance: false });
    expect(aboutContext(useAskOverlay.getState().about!).origin).toBe("chat_about");
    useAskOverlay.getState().aboutSent();
    expect(aboutContext(useAskOverlay.getState().about!)).toEqual({ origin: "ask_bar", subject: [workflow] });
  });

  it("removing the subject also drops the explicit context", () => {
    useAskOverlay.getState().startAbout(about, { inPlace: false, glance: false });
    useAskOverlay.getState().clearAbout();
    expect(useAskOverlay.getState()).toMatchObject({ about: null, explicitContext: null });
  });
});
