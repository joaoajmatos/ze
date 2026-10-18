import { describe, expect, it } from "vitest";
import { richTrace } from "./fixtures";
import { coordinateOf, METHOD_WORDS, routingFor } from "./routing";

const without = (...ids: string[]) => richTrace().judgments!.filter((j) => !ids.includes(j.question_id));

describe("routingFor", () => {
  it("embedding with no agent judgment: E5 score with the runner-up ghost", () => {
    const r = routingFor(richTrace({ judgments: without("agent") }));
    expect(r.bar).toMatchObject({ label: "E5 score", value: 0.72 });
    expect(r.bar?.ghost).toBeCloseTo(0.54);
  });

  it("clamps the ghost at zero", () => {
    expect(routingFor(richTrace({ judgments: [], confidence: 0.1, score_gap: 0.5 })).bar?.ghost).toBe(0);
  });

  it("embedding with a consumed agent judgment: Choice confidence, no ghost", () => {
    const r = routingFor(richTrace());
    expect(r.bar).toMatchObject({ label: "Choice confidence", value: 0.72, ghost: null });
  });

  it("an agent judgment that was not consumed falls back to E5 score", () => {
    const judgments = richTrace().judgments!.map((j) => (j.question_id === "agent" ? { ...j, consumed: false } : j));
    expect(routingFor(richTrace({ judgments })).bar?.label).toBe("E5 score");
  });

  it.each(["screen", "preset", "forced", "open_query"])("%s is fixed: no bar, no ghost", (method) => {
    const r = routingFor(richTrace({ routing_method: method }));
    expect(r.bar).toEqual({ label: "fixed", value: null, ghost: null });
  });

  it("haiku: the E5 score of the pick, no ghost", () => {
    expect(routingFor(richTrace({ routing_method: "haiku" })).bar).toMatchObject({ label: "E5 score of the pick", ghost: null });
  });

  it("fallback draws no bar", () => {
    expect(routingFor(richTrace({ routing_method: "fallback" })).bar).toBeNull();
  });

  it("draws no bar for a partial that has no judgments yet, only the agent and the method words", () => {
    const partial = routingFor(richTrace({ judgments: [], routing_method: "embedding" }), false);
    expect(partial.bar).toBeNull();
    expect(partial.methodWords).toBe("matched by meaning");
  });

  it("has words for every method", () => {
    for (const m of ["embedding", "haiku", "fallback", "screen", "open_query", "preset", "forced"]) expect(METHOD_WORDS[m]).toBeTruthy();
  });

  it("sorts the routing judgment's options by probability and marks the answer", () => {
    const r = routingFor(richTrace());
    expect(r.options.map((o) => [o.name, o.chosen])).toEqual([["companion", true], ["research", false], ["none", false]]);
  });

  it("reads the tier line", () => {
    expect(routingFor(richTrace()).tierLine).toBe("full · System One · anthropic/claude-sonnet");
    expect(routingFor(richTrace({ tier: null })).tierLine).toBeNull();
  });
});

describe("coordinateOf", () => {
  it("reads ask_bar, chat_about and a missing screen", () => {
    expect(coordinateOf(richTrace())).toBe("Asked from · Doing › Goal · Run 5k");
    expect(coordinateOf(richTrace({ screen: { origin: "chat_about", place: "doing", subject: ["Goal · Run 5k"] } }))).toBe("Asked about · Goal · Run 5k");
    expect(coordinateOf(richTrace({ screen: null }))).toBeNull();
  });
});

describe("routingFor shortlist", () => {
  const scored = () =>
    richTrace({
      routing_scores: [
        { agent: "companion", score: 0.83 },
        { agent: "research", score: 0.71 },
        { agent: "calendar", score: 0.4 },
      ],
      routing_thresholds: { threshold: 0.78, gap: 0.05 },
    });

  it("draws one bar per routing score against the thresholds, the picked agent marked", () => {
    const r = routingFor(scored());
    expect(r.scores.map((s) => [s.agent, s.score, s.chosen])).toEqual([["companion", 0.83, true], ["research", 0.71, false], ["calendar", 0.4, false]]);
    expect(r.thresholds).toEqual({ threshold: 0.78, gap: 0.05 });
  });

  it("shows the scores while the turn still streams", () => {
    expect(routingFor(scored(), false).scores).toHaveLength(3);
  });

  it("marks no threshold when there is no shortlist, even if the envelope carried one", () => {
    const r = routingFor(richTrace({ routing_scores: [], routing_thresholds: { threshold: 0.78, gap: 0.05 }, routing_method: "screen" }));
    expect(r.thresholds).toBeNull();
  });

  it("has an empty list, and the method, when routing used no embedding scores", () => {
    const r = routingFor(richTrace({ routing_scores: [], routing_thresholds: null, routing_method: "preset" }));
    expect(r.scores).toEqual([]);
    expect(r.thresholds).toBeNull();
    expect(r.methodWords).toBe("a preset question");
  });

  it("reads a trace before 187b as no scores", () => {
    expect(routingFor(richTrace()).scores).toEqual([]);
  });
});
