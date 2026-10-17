import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { useSendNotice } from "@/shared/lib";
import { INITIAL_PRESENCE, usePresenceStore } from "@/entities/presence";
import { askAbout, useAskOverlay } from "../model/ask-overlay";
import { AskBar } from "./AskBar";
import { useAskShortcut } from "./useAskShortcut";

function Harness() {
  useAskShortcut();
  return (
    <>
      <AskBar />
      <input aria-label="other" />
    </>
  );
}

function renderAt(at: string) {
  return render(
    <MemoryRouter initialEntries={[at]}>
      <Harness />
    </MemoryRouter>,
  );
}

const online = () => usePresenceStore.setState({ presence: { ...INITIAL_PRESENCE, offline: false, orb: "idle", phrase: "ready" } });

beforeEach(() => {
  useAskOverlay.getState().reset();
  usePresenceStore.getState().reset();
  online();
});

const input = () => screen.getByRole("textbox", { name: /Ask Ze/ });
const type = (text: string) => fireEvent.change(input(), { target: { value: text } });
const submit = () => fireEvent.submit(input().closest("form")!);

describe("AskBar", () => {
  it("submit opens the overlay and queues the text with the route context, without navigating", () => {
    renderAt("/doing/goals/g1");
    type("why is this slipping?");
    submit();
    const s = useAskOverlay.getState();
    expect(s.open).toBe(true);
    expect(s.outbox).toMatchObject({ text: "why is this slipping?", context: { place: "doing", route: "/doing/goals/g1" } });
    expect(input()).toHaveValue("");
  });

  it("keeps its text when a second submit is refused", () => {
    renderAt("/");
    type("one");
    submit();
    type("two");
    submit();
    expect(useAskOverlay.getState().outbox?.text).toBe("one");
    expect(input()).toHaveValue("two");
  });

  it("says so when a second message is refused", () => {
    renderAt("/");
    type("one");
    submit();
    type("two");
    submit();
    expect(useSendNotice.getState().notice).toMatch(/not sent your last message/);
  });

  it("is prefilled by askAbout without queueing", () => {
    renderAt("/doing/workflows/w1");
    act(() => askAbout({ text: "Why did this run fail?", context: { subject: [{ kind: "workflow_execution", id: "e1", parent_id: "w1" }] } }));
    expect(input()).toHaveValue("Why did this run fail?");
    expect(useAskOverlay.getState().outbox).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(useAskOverlay.getState().outbox?.context).toMatchObject({ subject: [{ kind: "workflow_execution", id: "e1", parent_id: "w1" }] });
  });

  it("is disabled while offline with the reason in its accessible name", () => {
    usePresenceStore.getState().dispatch({ type: "ws_closed" });
    renderAt("/");
    const field = screen.getByRole("textbox", { name: /Ze is offline/ });
    expect(field).toBeDisabled();
    expect(screen.getByRole("button", { name: /Ze is offline/ })).toBeDisabled();
  });

  it("has a disabled mic labelled for what is missing", () => {
    renderAt("/");
    expect(screen.getByRole("button", { name: "Voice input arrives later" })).toBeDisabled();
  });

  it("focuses on / outside inputs but not inside them", () => {
    renderAt("/");
    const outside = fireEvent.keyDown(document.body, { key: "/" });
    expect(outside).toBe(false);
    expect(input()).toHaveFocus();
    screen.getByLabelText("other").focus();
    const inside = fireEvent.keyDown(screen.getByLabelText("other"), { key: "/" });
    expect(inside).toBe(true);
    expect(screen.getByLabelText("other")).toHaveFocus();
  });

  it("tells the presence about focus, text and blur", () => {
    renderAt("/");
    fireEvent.focus(input());
    type("hi");
    expect(usePresenceStore.getState().presence.orb).toBe("listening");
    fireEvent.blur(input());
    expect(usePresenceStore.getState().presence.orb).toBe("idle");
  });
});
