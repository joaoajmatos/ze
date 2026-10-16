import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { JudgmentsSection } from "./JudgmentsSection";

function frame(
  overrides: Partial<WsTraceUpdateFrame> = {},
): WsTraceUpdateFrame {
  return {
    type: "trace_update",
    thread_id: "thread-a",
    message_id: "m1",
    agent: "companion",
    routing_method: "embedding",
    confidence: 0.8,
    score_gap: 0.1,
    is_compound: false,
    subtasks: ["companion"],
    memory_chunks: [],
    tool_calls: [],
    total_duration_ms: 10,
    skills_used: [],
    conductor_ledger: [],
    judgments: [],
    ...overrides,
  };
}

describe("JudgmentsSection", () => {
  it("hides when judgments are empty", () => {
    const { container } = render(<JudgmentsSection trace={frame()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows consumed vs unused and skip reason", () => {
    render(
      <JudgmentsSection
        trace={frame({
          judgments: [
            {
              question_id: "speech_act",
              kind: "choice",
              answer: "fact",
              latency_ms: 80,
              consumed: true,
              model: "typesafe/jev-1.13-20260917",
            },
            {
              question_id: "biography",
              kind: "noul",
              latency_ms: 5,
              consumed: false,
              skip_reason: "timeout",
            },
          ],
        })}
      />,
    );
    expect(screen.getByText("Judgments")).toBeInTheDocument();
    expect(screen.getByText("speech_act")).toBeInTheDocument();
    expect(screen.getByText("fact")).toBeInTheDocument();
    expect(screen.getByText("consumed")).toBeInTheDocument();
    expect(screen.getByText("skipped (timeout)")).toBeInTheDocument();
    expect(screen.getByText("unused")).toBeInTheDocument();
  });
});
