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

const arrivals = { route: 1_400, screen: 1_100, memory: 1_900, tier: 2_300, "tool:0": 2_800 };

describe("SignalPath", () => {
  it("starts at the origin and has one tick per stage with its offset", () => {
    render(<SignalPath trace={richTrace()} arrivals={arrivals} sentAt={1_000} streaming={false} />);
    expect(document.querySelector(".tr-origin")).not.toBeNull();
    const ticks = [...document.querySelectorAll(".tr-tick")].map((t) => t.getAttribute("data-stage"));
    expect(ticks).toEqual(["screen", "route", "memory", "tier", "tools"]);
    expect(screen.getByText("+0.1 s")).toBeInTheDocument();
    expect(screen.getByText("+1.8 s")).toBeInTheDocument();
  });

  it("marks the newest lit tick live while streaming and sweeps, and shows the reply as pending", () => {
    render(<SignalPath trace={richTrace({ tool_calls: [] })} arrivals={arrivals} sentAt={1_000} streaming />);
    expect(document.querySelectorAll("[data-live]")).toHaveLength(1);
    expect(document.querySelector("[data-live]")?.getAttribute("data-stage")).toBe("tier");
    expect(screen.getByTestId("signal-sweep")).toBeInTheDocument();
    expect(screen.getByLabelText("reply coming")).toBeInTheDocument();
  });

  it("settles without drawing a total the trace cannot prove", () => {
    render(<SignalPath trace={richTrace()} sentAt={null} streaming={false} />);
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.queryByTestId("signal-sweep")).toBeNull();
  });

  it("renders no sweep under reduced motion", () => {
    mm.set("(prefers-reduced-motion: reduce)", true);
    render(<SignalPath trace={richTrace()} sentAt={0} streaming />);
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

describe("JudgmentGauges", () => {
  it("groups by surface, gives skip reasons in words and a decision line", () => {
    render(<JudgmentGauges trace={richTrace()} />);
    expect(screen.getByRole("group", { name: "Routing" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "What Ze kept" })).toBeInTheDocument();
    expect(screen.getByText("skipped: the model's answer was not usable")).toBeInTheDocument();
    expect(screen.getByTestId("intake-decision")).toHaveTextContent("linked to the reminder it created this turn");
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

describe("Readouts and ReversalTrack", () => {
  it("shows the dot-matrix total, model, System One line and compaction", () => {
    render(<Readouts trace={richTrace()} />);
    expect(screen.getByRole("img", { name: "4200 milliseconds of tool time" })).toBeInTheDocument();
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
