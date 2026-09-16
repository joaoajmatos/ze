import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { ConductorSection } from "./ConductorSection";

function frame(
  overrides: Partial<WsTraceUpdateFrame> = {},
): WsTraceUpdateFrame {
  return {
    type: "trace_update",
    message_id: "m1",
    agent: "companion",
    routing_method: "haiku",
    confidence: 0.8,
    score_gap: 0.1,
    is_compound: false,
    subtasks: ["companion"],
    memory_chunks: [],
    tool_calls: [],
    total_duration_ms: 10,
    skills_used: [],
    ...overrides,
  };
}

describe("ConductorSection", () => {
  it("renders specialists and confirmation request_id", () => {
    render(
      <ConductorSection
        trace={frame({
          conductor_hint: [
            { agent: "calendar", intent: "read", prompt: "Tuesday" },
            { agent: "messenger", intent: "create", prompt: "mail" },
          ],
          conductor_ledger: [
            { agent: "calendar", status: "done" },
            {
              agent: "messenger",
              status: "awaiting_confirmation",
              request_id: "req-abc",
            },
          ],
        })}
      />,
    );
    expect(screen.getByText("Conductor")).toBeInTheDocument();
    expect(screen.getAllByText("calendar").length).toBeGreaterThan(0);
    expect(screen.getAllByText("messenger").length).toBeGreaterThan(0);
    expect(screen.getByText("req-abc")).toBeInTheDocument();
  });

  it("shows ask_user and skipped statuses", () => {
    render(
      <ConductorSection
        trace={frame({
          conductor_ledger: [
            { agent: "calendar", status: "skipped" },
            { agent: "loops", status: "ask_user" },
          ],
        })}
      />,
    );
    expect(screen.getByText("skipped")).toBeInTheDocument();
    expect(screen.getByText("ask_user")).toBeInTheDocument();
  });

  it("omits the section for independent parallel traces without conductor fields", () => {
    const { container } = render(
      <ConductorSection
        trace={frame({
          agent: "research",
          is_compound: true,
          subtasks: ["research", "news"],
          conductor_hint: null,
          conductor_ledger: [],
        })}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
