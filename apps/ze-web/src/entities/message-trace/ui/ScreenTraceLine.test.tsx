import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { screenTraceLine } from "../lib/screen-line";
import { ScreenTraceLine } from "./ScreenTraceLine";

const base = { origin: "ask_bar" as const, subject: [], selection_count: 0, visible_count: 0, canvas_count: 0, note_chars: 0, invalid: [], resolvers: [] };

describe("screenTraceLine", () => {
  it("names the subject for a chat about this", () => {
    expect(screenTraceLine({ ...base, origin: "chat_about", place: "doing", subject: ["Workflow · Weekly report"] })).toBe("Asked about: Workflow · Weekly report");
  });

  it("names the place and the first subject otherwise", () => {
    expect(screenTraceLine({ ...base, place: "doing", subject: ["Goal · LedgerLite", "Workflow · x"] })).toBe("Asked from: Doing · Goal · LedgerLite");
  });

  it("names the place alone with no subject", () => {
    expect(screenTraceLine({ ...base, place: "mind" })).toBe("Asked from: Mind");
  });

  it("is empty without a screen trace or anything to say", () => {
    expect(screenTraceLine(null)).toBeNull();
    expect(screenTraceLine(undefined)).toBeNull();
    expect(screenTraceLine(base)).toBeNull();
  });

  it("a chat_about trace without a subject falls back to the place", () => {
    expect(screenTraceLine({ ...base, origin: "chat_about", place: "world" })).toBe("Asked from: World");
  });
});

describe("ScreenTraceLine", () => {
  it("renders the line", () => {
    render(<ScreenTraceLine screen={{ ...base, place: "governance" }} />);
    expect(screen.getByTestId("screen-trace-line")).toHaveTextContent("Asked from: Governance");
  });

  it("renders nothing without a trace", () => {
    const { container } = render(<ScreenTraceLine screen={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});
