import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAskOverlay } from "../model/ask-overlay";
import { AboutPanel } from "./AboutPanel";

const about = { ref: { kind: "goal", id: "g1", label: "LedgerLite launch" }, origin: "chat_about" as const, suggestions: ["one?", "two?", "three?"] };

function setup(onPick = vi.fn()) {
  render(
    <>
      <AboutPanel inputSelector="[data-ask-input]" onPick={onPick} />
      <input data-ask-input="" aria-label="field" />
    </>,
  );
  return onPick;
}

beforeEach(() => useAskOverlay.getState().reset());

describe("AboutPanel", () => {
  it("renders nothing without a subject", () => {
    setup();
    expect(screen.queryByRole("group", { name: "Chat about" })).toBeNull();
  });

  it("shows the subject chip and three suggestions; a click picks one", () => {
    const onPick = setup();
    act(() => useAskOverlay.getState().startAbout(about, { inPlace: true, glance: false }));
    expect(screen.getByText("LedgerLite launch")).toBeInTheDocument();
    fireEvent.click(screen.getByText("two?"));
    expect(onPick).toHaveBeenCalledWith("two?");
  });

  it("keys 1-3 pick a suggestion while the field is focused and empty", () => {
    const onPick = setup();
    act(() => useAskOverlay.getState().startAbout(about, { inPlace: true, glance: false }));
    const field = screen.getByLabelText("field");
    field.focus();
    fireEvent.keyDown(field, { key: "3" });
    expect(onPick).toHaveBeenCalledWith("three?");
  });

  it("keys do nothing when the field has text or is not focused", () => {
    const onPick = setup();
    act(() => useAskOverlay.getState().startAbout(about, { inPlace: true, glance: false }));
    const field = screen.getByLabelText("field") as HTMLInputElement;
    fireEvent.keyDown(document.body, { key: "1" });
    field.focus();
    field.value = "typing";
    fireEvent.keyDown(field, { key: "1" });
    expect(onPick).not.toHaveBeenCalled();
  });

  it("the remove control drops the subject", () => {
    setup();
    act(() => useAskOverlay.getState().startAbout(about, { inPlace: true, glance: false }));
    fireEvent.click(screen.getByRole("button", { name: "Stop chatting about LedgerLite launch" }));
    expect(useAskOverlay.getState().about).toBeNull();
  });
});
