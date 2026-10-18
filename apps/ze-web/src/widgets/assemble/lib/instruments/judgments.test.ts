import { describe, expect, it } from "vitest";
import { richTrace } from "./fixtures";
import { describeIntakeOutcome, describeJudgments } from "./judgments";

describe("describeJudgments", () => {
  const d = describeJudgments(richTrace().judgments);

  it("groups rows by surface through the closed id map", () => {
    expect(d.groups.map((g) => g.surface)).toEqual(["routing", "tier", "intake"]);
    expect(d.groups.find((g) => g.surface === "intake")!.rows.map((r) => r.id)).toEqual(["commitment", "family"]);
  });

  it("handles intake_outcome before the Choice renderer: no probabilities", () => {
    expect(d.groups.flatMap((g) => g.rows).some((r) => r.id === "intake_outcome")).toBe(false);
    expect(d.outcome).toEqual({ kind: "link", reason: "turn_created", link: "reminder", words: "linked to the reminder it created this turn" });
  });

  it("shapes Choice, Noul and Score rows", () => {
    const routing = d.groups[0].rows[0];
    expect(routing).toMatchObject({ shape: "choice", answer: "companion", status: "used" });
    expect(routing.options[0]).toEqual({ name: "companion", probability: 0.7 });
    expect(d.groups[1].rows[0]).toMatchObject({ shape: "noul", value: 0.2 });
    const score = describeJudgments([{ question_id: "x_score", kind: "score", answer: 0.4, latency_ms: 1 }]);
    expect(score.groups[0].rows[0]).toMatchObject({ shape: "score", value: 0.4 });
  });

  it("says consumed versus skipped with the reason in words", () => {
    const family = d.groups[2].rows[1];
    expect(family.status).toBe("skipped");
    expect(family.reason).toBe("the model's answer was not usable");
  });

  it("humanises an unknown question id into the other group", () => {
    const u = describeJudgments([{ question_id: "needs_big_idea", kind: "noul", answer: 0.5, latency_ms: 1 }]);
    expect(u.groups[0]).toMatchObject({ surface: "other" });
    expect(u.groups[0].rows[0].label).toBe("Needs big idea");
  });
});

describe("describeIntakeOutcome", () => {
  it.each([
    ["persist_fact:fact", "persist_fact", "kept as a fact"],
    ["resolve_loop:resolved", "resolve_loop", "closed an open loop"],
    ["create_loop_declared:explicit", "create_loop_declared", "started tracking what you asked it to"],
    ["create_loop_suspected:open_concern", "create_loop_suspected", "noted a concern it suspects you have"],
    ["link:turn_created:goal", "link", "linked to the goal it created this turn"],
    ["hold:waiting_on", "hold", "held, nothing written"],
    ["fallback:uncalibrated", "fallback", "used the older extractor"],
  ])("%s", (answer, kind, words) => {
    expect(describeIntakeOutcome(answer)).toMatchObject({ kind, words });
  });

  it("reads hold:forget_not_created through the humanise fallback and unknown kinds as words", () => {
    expect(describeIntakeOutcome("hold:forget_not_created")?.words).toBe("held, nothing written (forget not created)");
    expect(describeIntakeOutcome("mystery:odd_reason")?.words).toBe("mystery (odd reason)");
    expect(describeIntakeOutcome(null)).toBeNull();
  });
});
