import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
// @ts-expect-error node builtin; this workspace has no @types/node
import { readFileSync } from "node:fs";
import { Module } from "./Module";

describe("Module with Chat about this", () => {
  it("names the chip after what the chat is about", () => {
    render(<Module label="Goal" chatAboutLabel="LedgerLite launch" onChatAbout={() => {}}>body</Module>);
    expect(screen.getByRole("button", { name: "Chat about LedgerLite launch" })).toBeInTheDocument();
  });

  it("falls back to the module label", () => {
    render(<Module label="Workflows" onChatAbout={() => {}}>body</Module>);
    expect(screen.getByRole("button", { name: "Chat about Workflows" })).toBeInTheDocument();
  });

  it("has no chip and ignores c without a handler", () => {
    render(<Module label="Goal"><button>inside</button></Module>);
    expect(screen.queryByRole("button", { name: /Chat about/ })).toBeNull();
    fireEvent.keyDown(screen.getByRole("button", { name: "inside" }), { key: "c" });
  });

  it("clicking the chip fires with the module's element", () => {
    const onChatAbout = vi.fn();
    render(<Module label="Goal" onChatAbout={onChatAbout}>body</Module>);
    fireEvent.click(screen.getByRole("button", { name: /Chat about/ }));
    expect(onChatAbout).toHaveBeenCalledTimes(1);
    expect(onChatAbout.mock.calls[0][0]).toBe(screen.getByRole("region", { name: "Goal" }));
  });

  it("c inside the module fires; c inside an input does not", () => {
    const onChatAbout = vi.fn();
    render(
      <Module label="Goal" onChatAbout={onChatAbout}>
        <button>row</button>
        <input aria-label="note" />
      </Module>,
    );
    fireEvent.keyDown(screen.getByRole("button", { name: "row" }), { key: "c" });
    expect(onChatAbout).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(screen.getByLabelText("note"), { key: "c" });
    expect(onChatAbout).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(screen.getByRole("button", { name: "row" }), { key: "c", ctrlKey: true });
    expect(onChatAbout).toHaveBeenCalledTimes(1);
  });

  it("is reachable by Tab: a plain button, never hidden from the accessibility tree", () => {
    render(<Module label="Goal" onChatAbout={() => {}}>body</Module>);
    const chip = screen.getByRole("button", { name: /Chat about/ });
    expect(chip).toHaveProperty("tabIndex", 0);
    expect(chip).not.toHaveAttribute("hidden");
    expect(chip).not.toHaveAttribute("aria-hidden");
  });
});

describe("chat-about styles", () => {
  // Vitest strips CSS imports, so read the stylesheet from disk (tests run from apps/ze-web).
  const css: string = readFileSync("src/shared/styles/ze.css", "utf8");
  const block = (query: string) => {
    const start = css.indexOf(`@media (${query})`, css.indexOf(".chat-about {"));
    expect(start).toBeGreaterThan(-1);
    let depth = 0;
    for (let i = css.indexOf("{", start); i < css.length; i++) {
      if (css[i] === "{") depth++;
      if (css[i] === "}" && --depth === 0) return css.slice(start, i + 1);
    }
    return "";
  };

  it("under hover: hover the chip waits with opacity and transform, never display or visibility", () => {
    const hover = block("hover: hover");
    expect(hover).toMatch(/opacity:\s*0/);
    expect(hover).not.toMatch(/display:\s*none|visibility:\s*hidden/);
    expect(hover).toMatch(/:focus-within \.chat-about/);
    expect(hover).toMatch(/\.chat-about:focus-visible/);
  });

  it("under hover: none it is shown with a 44 px target", () => {
    const none = block("hover: none");
    expect(none).toMatch(/min-height:\s*44px/);
    expect(none).not.toMatch(/opacity:\s*0/);
  });

  it("has no hiding rule outside the hover media query", () => {
    const head = css.slice(css.indexOf(".chat-about {"), css.indexOf("@media (hover: hover)", css.indexOf(".chat-about {")));
    expect(head).not.toMatch(/opacity:\s*0|display:\s*none|visibility:\s*hidden/);
  });
});
