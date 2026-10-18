import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { describe, expect, it } from "vitest";
import { whyFor } from "./why";

const trace = (over: Partial<WsTraceUpdateFrame> = {}) =>
  ({ routing_method: "embedding", tool_calls: [], ...over }) as WsTraceUpdateFrame;

describe("whyFor", () => {
  it("opens Routing for a preset reply", () => {
    expect(whyFor(trace({ routing_method: "preset" }))).toEqual({ section: "routing", highlight: [] });
  });

  it("opens Tools with the render and show rows highlighted otherwise", () => {
    const t = trace({
      tool_calls: [
        { name: "show_slipping", call_index: 0 },
        { name: "get_goals", call_index: 1 },
        { name: "render_table", call_index: 2 },
      ] as never,
    });
    expect(whyFor(t)).toEqual({ section: "tools", highlight: ["show_slipping", "render_table"] });
  });

  it("returns null with no trace", () => {
    expect(whyFor(undefined)).toBeNull();
  });
});
