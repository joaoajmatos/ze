import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TraceEntry } from "./TraceEntry";

function frame(extra: Record<string, unknown> = {}): WsTraceUpdateFrame {
  return {
    type: "trace_update",
    thread_id: "thread-a",
    message_id: "m1",
    agent: "calendar",
    routing_method: "embedding",
    confidence: 0.9,
    score_gap: 0.2,
    is_compound: false,
    subtasks: [],
    memory_chunks: [],
    tool_calls: [],
    total_duration_ms: 12,
    skills_used: [],
    ...extra,
  } as WsTraceUpdateFrame;
}

describe("TraceEntry confirmations", () => {
  it("shows the Confirmations section when the trace has outcomes", () => {
    render(
      <TraceEntry
        index={0}
        defaultOpen
        trace={frame({
          write_confirmations: [
            {
              request_id: "req-1",
              round: 1,
              item_id: "c1",
              agent: "calendar",
              tool: "delete_event",
              summary: "Dentist",
              outcome: "denied",
            },
          ],
        })}
      />,
    );
    expect(screen.getByText("Confirmations")).toBeInTheDocument();
    expect(screen.getByText("Denied")).toBeInTheDocument();
  });

  it("hides it when no write was confirmed", () => {
    render(<TraceEntry index={0} defaultOpen trace={frame()} />);
    expect(screen.queryByText("Confirmations")).not.toBeInTheDocument();
  });
});
