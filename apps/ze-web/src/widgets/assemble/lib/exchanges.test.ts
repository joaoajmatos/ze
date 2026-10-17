import type { MessageSchema as Message } from "@myguyze/ze-client";
import { describe, expect, it } from "vitest";
import { groupExchanges, spanOf } from "./exchanges";

const m = (id: string, role: "user" | "assistant", over: Partial<Message> = {}): Message => ({
  id,
  role,
  text: id,
  components: [],
  read: true,
  thread_id: "t",
  created_at: `2026-10-18T10:0${id.length}:00Z`,
  ...over,
});

describe("groupExchanges", () => {
  it("pairs a user line with the assistant messages that follow", () => {
    const ex = groupExchanges([m("u", "user"), m("a", "assistant"), m("ab", "assistant"), m("u2", "user"), m("a2", "assistant")]);
    expect(ex.map((e) => [e.user?.id ?? null, e.replies.map((r) => r.id)])).toEqual([
      ["u", ["a", "ab"]],
      ["u2", ["a2"]],
    ]);
  });

  it("makes an assistant message with no user line its own unprompted exchange", () => {
    const ex = groupExchanges([m("a", "assistant"), m("u", "user"), m("ab", "assistant")]);
    expect(ex[0]).toMatchObject({ user: null, unprompted: true });
    expect(ex[1].unprompted).toBe(false);
  });

  it("hides a reply a retry replaced", () => {
    const ex = groupExchanges([m("u", "user"), m("a", "assistant", { replaced_by: "b" }), m("b", "assistant")]);
    expect(ex[0].replies.map((r) => r.id)).toEqual(["b"]);
  });

  it("keeps a user line that has no reply yet", () => {
    expect(groupExchanges([m("u", "user")])).toEqual([expect.objectContaining({ user: expect.objectContaining({ id: "u" }), replies: [] })]);
  });
});

describe("spanOf", () => {
  it("spans by component type and collapses when compact", () => {
    expect(spanOf("headline", false)).toBe(12);
    expect(spanOf("claim_card", false)).toBe(4);
    expect(spanOf("claim_timeline", false)).toBe(12);
    expect(spanOf("chart", false)).toBe(8);
    expect(spanOf("table", false)).toBe(8);
    expect(spanOf("text", false)).toBe(6);
    expect(spanOf("claim_card", true)).toBe(12);
  });
});
