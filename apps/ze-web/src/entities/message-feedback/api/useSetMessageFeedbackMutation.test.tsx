import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { MessageFeedback } from "../model/types";
import { useMessageFeedbackQuery } from "./useMessageFeedbackQuery";
import { useSetMessageFeedbackMutation } from "./useSetMessageFeedbackMutation";

const { fetchMessageFeedback, putMessageFeedback } = vi.hoisted(() => ({
  fetchMessageFeedback: vi.fn(),
  putMessageFeedback: vi.fn(),
}));
vi.mock("./feedbackApi", () => ({ fetchMessageFeedback, putMessageFeedback }));

function view(overrides: Partial<MessageFeedback> = {}): MessageFeedback {
  return {
    message_id: "m1",
    current: null,
    history: [],
    retry: { available: true, reason_code: null, reason_text: null },
    replaces: null,
    replaced_by: null,
    trace_present: true,
    ...overrides,
  };
}

function setup() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return renderHook(
    () => ({
      feedback: useMessageFeedbackQuery(["m1"]),
      mutation: useSetMessageFeedbackMutation(),
    }),
    { wrapper },
  );
}

describe("message feedback entity", () => {
  beforeEach(() => {
    fetchMessageFeedback.mockReset();
    putMessageFeedback.mockReset();
    fetchMessageFeedback.mockResolvedValue([view()]);
  });

  it("loads feedback keyed by message id", async () => {
    const { result } = setup();
    await waitFor(() => expect(result.current.feedback.byId.get("m1")).toBeDefined());
    expect(fetchMessageFeedback).toHaveBeenCalledWith(["m1"]);
  });

  it("applies the rating optimistically, before the server answers", async () => {
    let resolve!: (v: MessageFeedback) => void;
    putMessageFeedback.mockReturnValue(new Promise((r) => (resolve = r)));
    const { result } = setup();
    await waitFor(() => expect(result.current.feedback.byId.size).toBe(1));

    act(() => result.current.mutation.mutate({ messageId: "m1", rating: "up", idempotencyKey: "k1" }));
    await waitFor(() => expect(result.current.feedback.byId.get("m1")?.current).toBe("up"));
    expect(result.current.feedback.byId.get("m1")?.history.at(-1)?.kind).toBe("thumbs_up");

    fetchMessageFeedback.mockResolvedValue([view({ current: "up" })]);
    await act(async () => resolve(view({ current: "up" })));
  });

  it("reverts to the previous state when saving fails", async () => {
    putMessageFeedback.mockRejectedValue(new Error("boom"));
    const { result } = setup();
    await waitFor(() => expect(result.current.feedback.byId.size).toBe(1));

    await act(async () => {
      await result.current.mutation
        .mutateAsync({ messageId: "m1", rating: "down", idempotencyKey: "k2" })
        .catch(() => undefined);
    });
    await waitFor(() => expect(result.current.feedback.byId.get("m1")?.current).toBeNull());
    expect(result.current.feedback.byId.get("m1")?.history).toEqual([]);
  });

  it("sends the idempotency key and rating to the API", async () => {
    putMessageFeedback.mockResolvedValue(view({ current: null }));
    const { result } = setup();
    await waitFor(() => expect(result.current.feedback.byId.size).toBe(1));
    await act(async () => {
      await result.current.mutation.mutateAsync({
        messageId: "m1",
        rating: "none",
        idempotencyKey: "k3",
      });
    });
    expect(putMessageFeedback).toHaveBeenCalledWith({
      messageId: "m1",
      rating: "none",
      idempotencyKey: "k3",
    });
  });
});
