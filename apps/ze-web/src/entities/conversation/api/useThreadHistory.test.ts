import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useConversation } from "../model/store";
import { useThreadHistory } from "./useThreadHistory";

const m = vi.hoisted(() => ({ listMessages: vi.fn(), send: vi.fn() }));
vi.mock("@myguyze/ze-client", () => ({ listMessages: m.listMessages }));
vi.mock("@/shared/api", () => ({ send: m.send }));

const msg = (id: string, over = {}) => ({
  id,
  role: "assistant",
  text: id,
  components: [],
  read: true,
  thread_id: "t1",
  created_at: `2026-10-18T10:0${id}:00Z`,
  ...over,
});

beforeEach(() => {
  useConversation.setState({ byThread: {} });
  m.listMessages.mockReset();
  m.send.mockReset();
});

describe("useThreadHistory", () => {
  it("loads once, writes history_loaded and acks unread assistant replies", async () => {
    m.listMessages.mockResolvedValue({ data: [msg("1"), msg("2", { read: false })] });
    const { result } = renderHook(() => useThreadHistory("t1"));
    await act(() => result.current.loadHistory());
    await act(() => result.current.loadHistory());
    expect(m.listMessages).toHaveBeenCalledTimes(1);
    expect(useConversation.getState().byThread.t1.messages.map((x) => x.id)).toEqual(["1", "2"]);
    expect(m.send).toHaveBeenCalledWith({ type: "ack", ids: ["2"] });
  });

  it("reload returns the new history", async () => {
    m.listMessages.mockResolvedValueOnce({ data: [msg("1")] }).mockResolvedValueOnce({ data: [msg("1"), msg("2")] });
    const { result } = renderHook(() => useThreadHistory("t1"));
    await act(() => result.current.loadHistory());
    let history: unknown;
    await act(async () => {
      history = await result.current.reload();
    });
    expect((history as unknown[]).length).toBe(2);
  });

  it("loads again for another thread", async () => {
    m.listMessages.mockResolvedValue({ data: [] });
    const { result, rerender } = renderHook(({ id }) => useThreadHistory(id), { initialProps: { id: "t1" } });
    await act(() => result.current.loadHistory());
    rerender({ id: "t2" });
    await act(() => result.current.loadHistory());
    await waitFor(() => expect(m.listMessages).toHaveBeenCalledTimes(2));
    expect(useConversation.getState().byThread.t2.historyLoaded).toBe(true);
  });
});
