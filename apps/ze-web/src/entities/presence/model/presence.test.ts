import { describe, expect, it } from "vitest";
import { INITIAL_PRESENCE, nextPresence, type PresenceEvent, type PresenceState } from "./presence";

const T0 = 1_000;

function run(events: (PresenceEvent | [PresenceEvent, number])[], from: PresenceState = INITIAL_PRESENCE): PresenceState {
  return events.reduce<PresenceState>((s, e) => (Array.isArray(e) ? nextPresence(s, e[0], e[1]) : nextPresence(s, e, T0)), from);
}

const online = run([{ type: "ws_open" }]);

describe("nextPresence", () => {
  it("starts offline until the socket opens", () => {
    expect(INITIAL_PRESENCE.orb).toBe("error");
    expect(online.orb).toBe("idle");
  });

  it("ws_closed from any state is error with the phrase Offline", () => {
    for (const events of [[], [{ type: "turn_thinking" }], [{ type: "turn_thinking" }, { type: "turn_token" }], [{ type: "ask_focus" }, { type: "ask_text", nonEmpty: true }]] as PresenceEvent[][]) {
      const s = run([...events, { type: "ws_closed" }], online);
      expect(s.orb).toBe("error");
      expect(s.phrase).toBe("Offline");
    }
  });

  it("ws_open from error is idle", () => {
    const s = run([{ type: "ws_closed" }, { type: "ws_open" }], online);
    expect(s.orb).toBe("idle");
  });

  it("turn_thinking carries the phrase", () => {
    const s = run([{ type: "turn_thinking", text: "Looking at your calendar" }], online);
    expect(s.orb).toBe("thinking");
    expect(s.phrase).toBe("Looking at your calendar");
    expect(run([{ type: "turn_thinking" }], online).phrase).toBe("thinking");
  });

  it("turn_token is speaking", () => {
    expect(run([{ type: "turn_thinking" }, { type: "turn_token" }], online).orb).toBe("speaking");
  });

  it("turn_message blooms done, then settles to idle after 1 s", () => {
    const s = run([{ type: "turn_thinking" }, { type: "turn_token" }, [{ type: "turn_message" }, T0]], online);
    expect(s.orb).toBe("done");
    expect(s.doneUntil).toBe(T0 + 1000);
    expect(nextPresence(s, { type: "settle" }, T0 + 999).orb).toBe("done");
    expect(nextPresence(s, { type: "settle" }, T0 + 1000).orb).toBe("idle");
  });

  it("turn_message from idle stays idle", () => {
    expect(run([{ type: "turn_message" }], online).orb).toBe("idle");
  });

  it("ask focus plus text is listening; blur returns to idle unless a turn is in flight", () => {
    const listening = run([{ type: "ask_focus" }, { type: "ask_text", nonEmpty: true }], online);
    expect(listening.orb).toBe("listening");
    expect(listening.phrase).toBe("listening");
    expect(nextPresence(listening, { type: "ask_blur" }, T0).orb).toBe("idle");
    const busy = run([{ type: "ask_focus" }, { type: "ask_text", nonEmpty: true }, { type: "turn_thinking" }, { type: "ask_blur" }], online);
    expect(busy.orb).toBe("thinking");
  });

  it("ask focus alone is not listening", () => {
    expect(run([{ type: "ask_focus" }], online).orb).toBe("idle");
  });

  it("turn_error returns to idle with no phrase", () => {
    const s = run([{ type: "turn_thinking", text: "x" }, { type: "turn_error" }], online);
    expect(s.orb).toBe("idle");
    expect(s.phrase).toBe("ready");
  });

  it("turn_reset drops an in-flight turn", () => {
    expect(run([{ type: "turn_thinking" }, { type: "turn_reset" }], online).orb).toBe("idle");
  });

  it("a world signal shows only when no turn or ask is active, and clears", () => {
    const s = run([{ type: "set_world_signal", orb: "attention" }], online);
    expect(s.orb).toBe("attention");
    expect(run([{ type: "set_world_signal", orb: "attention" }, { type: "turn_thinking" }], online).orb).toBe("thinking");
    expect(run([{ type: "set_world_signal", orb: "attention" }, { type: "set_world_signal", orb: null }], online).orb).toBe("idle");
  });

  it("offline wins over everything", () => {
    const s = run([{ type: "set_world_signal", orb: "attention" }, { type: "ws_closed" }, { type: "turn_thinking" }], online);
    expect(s.orb).toBe("error");
  });
});
