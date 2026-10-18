import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { mockMatchMedia } from "@/test/match-media";
import { richTrace } from "../../lib/instruments/fixtures";
import { JudgmentGauges } from "./JudgmentGauges";
import { MemoryConstellation } from "./MemoryConstellation";
import { Readouts } from "./Readouts";
import { ReversalTrack } from "./ReversalTrack";
import { RoutingInstrument } from "./RoutingInstrument";
import { SignalPath } from "./SignalPath";
import { ToolsTimeline } from "./ToolsTimeline";

let mm: ReturnType<typeof mockMatchMedia>;
beforeEach(() => {
  mm = mockMatchMedia({ "(prefers-reduced-motion: reduce)": false, "(max-width: 1023px)": false });
});
afterEach(() => mm.restore());

describe("SignalPath", () => {
  it("starts at the origin and has one tick per server stage with its offset", () => {
    render(<SignalPath trace={richTrace()} streaming={false} />);
    expect(document.querySelector(".tr-origin")).not.toBeNull();
    const ticks = [...document.querySelectorAll(".tr-tick")].map((t) => t.getAttribute("data-stage"));
    expect(ticks).toEqual(["preprocess", "screen", "route", "memory", "skills", "tier", "preflight", "execute", "synthesize", "trace", "memory write"]);
    expect(screen.getAllByText("+0.0 s")).toHaveLength(3);
    expect(screen.getByText("+1.4 s")).toBeInTheDocument();
  });

  it("marks a second run with the time spent waiting for you", () => {
    const stages = [
      { name: "await_write_confirmation", start_ms: 290, duration_ms: 0, run: 1 },
      { name: "execute_tool", start_ms: 0, duration_ms: 400, run: 2 },
    ];
    render(<SignalPath trace={richTrace({ stages, paused_ms: 12_000 })} streaming={false} />);
    expect(screen.getByText("waited 12.0 s")).toBeInTheDocument();
  });

  it("marks the newest lit tick live while streaming and sweeps, and shows the reply as pending", () => {
    render(<SignalPath trace={richTrace({ stages: richTrace().stages!.slice(0, 6) })} streaming />);
    expect(document.querySelectorAll("[data-live]")).toHaveLength(1);
    expect(document.querySelector("[data-live]")?.getAttribute("data-stage")).toBe("tier");
    expect(screen.getByTestId("signal-sweep")).toBeInTheDocument();
    expect(screen.getByLabelText("reply coming")).toBeInTheDocument();
  });

  it("draws a trace without stages with no offsets", () => {
    render(<SignalPath trace={richTrace({ stages: undefined })} streaming={false} />);
    expect(document.querySelectorAll(".tr-tick")).toHaveLength(5);
    expect(screen.queryByText(/^\+\d/)).toBeNull();
    expect(screen.queryByTestId("signal-sweep")).toBeNull();
  });

  it("renders no sweep under reduced motion", () => {
    mm.set("(prefers-reduced-motion: reduce)", true);
    render(<SignalPath trace={richTrace()} streaming />);
    expect(screen.queryByTestId("signal-sweep")).toBeNull();
  });
});

describe("RoutingInstrument", () => {
  it("draws the bar, the options with the chosen marked, the tier line and the coordinate; never a threshold", () => {
    render(<RoutingInstrument trace={richTrace({ judgments: richTrace().judgments!.filter((j) => j.question_id !== "agent") })} />);
    expect(screen.getByRole("meter", { name: "E5 score" })).toHaveAttribute("aria-valuenow", "72");
    expect(screen.getByText(/runner-up 54%/)).toBeInTheDocument();
    expect(screen.getByText("full · System One · anthropic/claude-sonnet")).toBeInTheDocument();
    expect(screen.getByTestId("coordinate")).toHaveTextContent("Asked from · Doing › Goal · Run 5k");
    expect(document.querySelector("[class*=threshold]")).toBeNull();
  });

  it("marks the chosen option and has no ghost for a consumed Choice", () => {
    render(<RoutingInstrument trace={richTrace()} />);
    expect(document.querySelector(".tr-ghost")).toBeNull();
    expect(document.querySelector("[data-chosen]")).toHaveTextContent("companion");
  });
});

describe("RoutingInstrument shortlist", () => {
  it("draws one meter per score with the threshold marked", () => {
    render(<RoutingInstrument trace={richTrace({ routing_scores: [{ agent: "companion", score: 0.83 }, { agent: "research", score: 0.71 }], routing_thresholds: { threshold: 0.78, gap: 0.05 } })} />);
    const meters = within(screen.getByRole("list", { name: "Shortlist scores" })).getAllByRole("meter");
    expect(meters.map((m) => m.getAttribute("aria-valuenow"))).toEqual(["83", "71"]);
    expect(document.querySelectorAll(".tr-threshold").length).toBeGreaterThan(0);
    expect(screen.getByText("threshold 78% · gap 5%")).toBeInTheDocument();
  });

  it("draws no shortlist for an empty list", () => {
    render(<RoutingInstrument trace={richTrace({ routing_scores: [] })} />);
    expect(screen.queryByRole("list", { name: "Shortlist scores" })).toBeNull();
  });
});

describe("JudgmentGauges", () => {
  it("groups by surface, gives skip reasons in words and a decision line", () => {
    render(<JudgmentGauges trace={richTrace()} />);
    expect(screen.getByRole("group", { name: "Routing" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "What Ze kept" })).toBeInTheDocument();
    expect(screen.getByText("skipped: the model's answer was not usable")).toBeInTheDocument();
    expect(screen.getByTestId("intake-decision")).toHaveTextContent("linked to the reminder it created this turn");
  });

  it("marks the bar on a gauge and reads a surface without one as uncalibrated", () => {
    render(<JudgmentGauges trace={richTrace()} />);
    expect(screen.getByText("bar choice_trust 50%")).toBeInTheDocument();
    expect(screen.getAllByText("uncalibrated")).toHaveLength(1);
  });
});

describe("MemoryConstellation", () => {
  it("draws one mark per chunk, shows text on focus, and moves with arrow keys", () => {
    render(<MemoryConstellation chunks={richTrace().memory_chunks} />);
    const marks = screen.getAllByRole("img");
    expect(marks).toHaveLength(5);
    act(() => marks[0].focus());
    expect(screen.getByText("Runs on Tuesdays")).toBeInTheDocument();
    fireEvent.keyDown(marks[0], { key: "ArrowRight" });
    const byScore = [...marks].sort((a, b) => a.getAttribute("aria-label")!.localeCompare(b.getAttribute("aria-label")!));
    expect(byScore.length).toBe(5);
  });

  it("renders the ranked list on a phone", () => {
    mm.set("(max-width: 1023px)", true);
    render(<MemoryConstellation chunks={richTrace().memory_chunks} />);
    const list = screen.getByRole("list", { name: /most relevant first/ });
    expect(within(list).getAllByRole("listitem")[0]).toHaveTextContent("Runs on Tuesdays");
  });
});

describe("ToolsTimeline", () => {
  it("draws lanes on separate axes with the caption, delegate note, and text marks", () => {
    render(<ToolsTimeline trace={richTrace()} />);
    expect(screen.getAllByRole("group").map((g) => g.getAttribute("aria-label"))).toEqual(["companion tools", "calendar tools", "messenger tools"]);
    expect(screen.getByText("order and duration per lane; start times not recorded")).toBeInTheDocument();
    expect(screen.getByText("includes the delegate's calls")).toBeInTheDocument();
    expect(screen.getAllByText("irreversible")).toHaveLength(2);
    expect(screen.getByText("approved")).toBeInTheDocument();
    expect(screen.getByText("denied")).toBeInTheDocument();
  });

  it("reads 'returned' for a live call and highlights the rows that drew modules", () => {
    render(<ToolsTimeline trace={richTrace()} partial highlight={["get_goals"]} />);
    expect(screen.getAllByText("returned").length).toBeGreaterThan(0);
    expect(document.querySelector("[data-highlight]")).toHaveTextContent("get_goals");
  });
});

describe("ToolsTimeline on live rows", () => {
  const live = (over: Record<string, unknown>) => ({ name: "send_email", agent: "messenger", duration_ms: 0, success: true, result_snippet: "", access: "write", start_offset_ms: 640, ...over });

  it("says a parked call is waiting for you, and replaces it with its approved run", () => {
    const { rerender } = render(<ToolsTimeline trace={richTrace({ tool_calls: [live({ call_id: "c1", gate: "parked" })] as never })} partial />);
    expect(screen.getByText("waiting for you")).toBeInTheDocument();
    rerender(<ToolsTimeline trace={richTrace({ tool_calls: [live({ call_id: "c1", gate: "approved", duration_ms: 300 })] as never })} partial />);
    expect(screen.queryByText("waiting for you")).toBeNull();
    expect(screen.getByText("approved")).toBeInTheDocument();
    expect(screen.getAllByText("send_email")).toHaveLength(1);
  });

  it("shows a failed live row as failed", () => {
    render(<ToolsTimeline trace={richTrace({ tool_calls: [live({ call_id: "c2", success: false })] as never })} partial />);
    expect(screen.getByText("failed")).toBeInTheDocument();
  });
});

describe("Readouts and ReversalTrack", () => {
  it("shows the total, active and tool time, tokens, cost and context fill", () => {
    render(<Readouts trace={richTrace({ paused_ms: 1000 })} />);
    expect(screen.getByRole("img", { name: "6000 milliseconds for the whole turn" })).toBeInTheDocument();
    expect(screen.getByText("5.0 s")).toBeInTheDocument();
    expect(screen.getByText("4.2 s")).toBeInTheDocument();
    expect(screen.getByText("9,920 in · 500 out")).toBeInTheDocument();
    expect(screen.getByText("$0.0356")).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: "Context fill" })).toHaveAttribute("aria-valuenow", "3");
    expect(screen.getByText("1,840 tokens")).toBeInTheDocument();
  });

  it("says partial for a total the recorder lost the start of", () => {
    render(<Readouts trace={richTrace({ telemetry_partial: true })} />);
    expect(screen.getByText("partial")).toBeInTheDocument();
  });

  it("marks estimated usage and clamps an over-full context bar", () => {
    render(<Readouts trace={richTrace({ usage: { ...richTrace().usage!, estimated: true, context_fill: 1.4 } })} />);
    expect(screen.getAllByText(/est\./).length).toBeGreaterThan(0);
    expect(screen.getByRole("meter", { name: "Context fill" })).toHaveAttribute("aria-valuenow", "100");
    expect(screen.getByText("140%")).toBeInTheDocument();
  });

  it("shows the model name only without usage", () => {
    render(<Readouts trace={richTrace({ usage: null })} />);
    expect(screen.getByText("anthropic/claude-sonnet")).toBeInTheDocument();
    expect(screen.queryByText(/ in · /)).toBeNull();
  });

  it("shows no time for a trace before 187b, not a tool time of zero", () => {
    render(<Readouts trace={richTrace({ turn_duration_ms: null, usage: null })} />);
    expect(screen.queryByText("Tool time")).toBeNull();
    expect(screen.queryByText("Total")).toBeNull();
  });

  it("shows the model, System One line and compaction", () => {
    render(<Readouts trace={richTrace()} />);
    expect(screen.getByText("anthropic/claude-sonnet")).toBeInTheDocument();
    expect(screen.getByText("System One: 3 requests, 870 ms, 2,100 input tokens")).toBeInTheDocument();
    expect(screen.getByText("messages 0–6 summarised")).toBeInTheDocument();
  });

  it("lists undone entries last action first with outcomes in words", () => {
    render(
      <ReversalTrack
        rollback={{
          state: "partial",
          entries: [
            { entry_id: "a", tool: "x", effect_phrase: "set a reminder", outcome: "undone" },
            { entry_id: "b", tool: "y", effect_phrase: "create a goal", outcome: "failed" },
          ],
        } as never}
      />,
    );
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("create a goal");
    expect(items[0]).toHaveTextContent("could not be undone");
    expect(items[1]).toHaveTextContent("undone");
  });

  it("uses no coral class anywhere in the instruments", () => {
    const { container } = render(
      <>
        <RoutingInstrument trace={richTrace()} />
        <JudgmentGauges trace={richTrace()} />
        <ToolsTimeline trace={richTrace()} />
        <Readouts trace={richTrace()} />
      </>,
    );
    expect(container.innerHTML).not.toMatch(/\bhot\b|coral/);
  });
});

describe("ToolsTimeline script rows", () => {
  const base = { result_snippet: "", success: true, agent: "companion", start_offset_ms: 0 };
  const scriptTrace = (cut = false) =>
    richTrace({
      tool_calls: [
        { ...base, name: "run_tool_script", call_id: "s1", access: "script", duration_ms: 420, script: { source: "goals = get_goals()\nreturn goals", source_cut: cut, outcome: "ok", limit: null } },
        { ...base, name: "get_goals", call_id: "i1", parent_call_id: "s1", access: "read", duration_ms: 12 },
        { ...base, name: "get_loops", call_id: "i2", parent_call_id: "s1", access: "read", duration_ms: 9 },
      ] as never,
    });

  it("draws the summary collapsed with no source or children", () => {
    render(<ToolsTimeline trace={scriptTrace()} />);
    const toggle = screen.getByRole("button", { name: /Script · ok · 2 calls · 420 ms/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText(/goals = get_goals/)).toBeNull();
    expect(screen.queryByText("get_goals")).toBeNull();
  });

  it("expands to the source in a monospace block and the child rows, with a cut note", () => {
    render(<ToolsTimeline trace={scriptTrace(true)} />);
    fireEvent.click(screen.getByRole("button", { name: /Script · ok/ }));
    expect(screen.getByRole("button", { name: /Script · ok/ })).toHaveAttribute("aria-expanded", "true");
    expect(document.querySelector("pre.tr-script-src")).toHaveTextContent("goals = get_goals()");
    expect(screen.getByText("get_goals")).toBeInTheDocument();
    expect(screen.getByText("get_loops")).toBeInTheDocument();
    expect(screen.getByText(/cut/i)).toBeInTheDocument();
  });

  it("shows no cut note when the source is whole, and toggles with Enter and Space", () => {
    render(<ToolsTimeline trace={scriptTrace()} />);
    const toggle = screen.getByRole("button", { name: /Script · ok/ });
    expect(toggle.tagName).toBe("BUTTON");
    fireEvent.click(toggle);
    expect(screen.queryByText(/cut/i)).toBeNull();
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });
});
