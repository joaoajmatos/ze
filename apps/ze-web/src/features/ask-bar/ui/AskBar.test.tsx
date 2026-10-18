import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({ place: vi.fn(), onSubmit: vi.fn((_t: string, _c: unknown, _p?: unknown) => true) }));
vi.mock("@/entities/workspace", () => ({ placeWorkspaceFile: m.place }));
import { useSendNotice } from "@/shared/lib";
import { INITIAL_PRESENCE, usePresenceStore } from "@/entities/presence";
import { askAbout, useAskOverlay } from "../model/ask-overlay";
import { AskBar } from "./AskBar";
import { useAskShortcut } from "./useAskShortcut";

function Harness({ disabledReason }: { disabledReason?: string | null }) {
  useAskShortcut();
  return (
    <>
      <AskBar onSubmit={m.onSubmit} disabledReason={disabledReason} />
      <input aria-label="other" />
    </>
  );
}

function renderAt(at: string, disabledReason?: string | null) {
  return render(
    <MemoryRouter initialEntries={[at]}>
      <Harness disabledReason={disabledReason} />
    </MemoryRouter>,
  );
}

const online = () => usePresenceStore.setState({ presence: { ...INITIAL_PRESENCE, offline: false, orb: "idle", phrase: "ready" } });

beforeEach(() => {
  m.place.mockReset();
  m.onSubmit.mockReset();
  m.onSubmit.mockReturnValue(true);
  useSendNotice.getState().clearNotice();
  useAskOverlay.getState().reset();
  usePresenceStore.getState().reset();
  online();
});

const input = () => screen.getByRole("textbox", { name: /Ask Ze/ });
const type = (text: string) => fireEvent.change(input(), { target: { value: text } });
const submit = () => fireEvent.submit(input().closest("form")!);

describe("AskBar", () => {
  it("hands the text, the explicit context and no files to onSubmit, then clears", () => {
    renderAt("/doing/goals/g1");
    type("why is this slipping?");
    submit();
    expect(m.onSubmit).toHaveBeenCalledWith("why is this slipping?", null, undefined);
    expect(input()).toHaveValue("");
  });

  it("keeps its text and says so when onSubmit refuses", () => {
    m.onSubmit.mockReturnValue(false);
    renderAt("/");
    type("two");
    submit();
    expect(input()).toHaveValue("two");
    expect(useSendNotice.getState().notice).toMatch(/not sent your last message/);
  });

  it("renders on /ask too, and is disabled with the given reason", () => {
    renderAt("/ask", "Ze is open in another window");
    const field = screen.getByRole("textbox", { name: /Ze is open in another window/ });
    expect(field).toBeDisabled();
  });

  it("attaches files to the workspace, sends the chips with the message, and clears them", async () => {
    m.place.mockResolvedValue({ path: "notes.txt", size: 12 });
    renderAt("/ask");
    const file = new File(["x"], "notes.txt");
    fireEvent.change(screen.getByLabelText("Attach file to workspace input"), { target: { files: [file] } });
    await waitFor(() => expect(screen.getByText("notes.txt")).toBeInTheDocument());
    type("read this");
    submit();
    expect(m.onSubmit).toHaveBeenCalledWith("read this", null, [{ path: "notes.txt", size: 12 }]);
    expect(screen.queryByText("notes.txt")).toBeNull();
  });

  it("says so when placing a file fails", async () => {
    m.place.mockRejectedValue(new Error("no"));
    renderAt("/ask");
    fireEvent.change(screen.getByLabelText("Attach file to workspace input"), { target: { files: [new File(["x"], "a.txt")] } });
    await waitFor(() => expect(useSendNotice.getState().notice).toBe("Could not place the file in the workspace."));
  });

  it("is prefilled by askAbout without queueing", () => {
    renderAt("/doing/workflows/w1");
    act(() => askAbout({ text: "Why did this run fail?", context: { subject: [{ kind: "workflow_execution", id: "e1", parent_id: "w1" }] } }));
    expect(input()).toHaveValue("Why did this run fail?");
    expect(m.onSubmit).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(m.onSubmit).toHaveBeenCalledWith("Why did this run fail?", { subject: [{ kind: "workflow_execution", id: "e1", parent_id: "w1" }] }, undefined);
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
