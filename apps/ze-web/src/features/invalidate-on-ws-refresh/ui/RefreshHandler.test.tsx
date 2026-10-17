import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { queryKeys } from "@/shared/lib";
import { RefreshHandler } from "./RefreshHandler";

const { useFrame } = vi.hoisted(() => ({ useFrame: vi.fn() }));

vi.mock("@/shared/api", () => ({ useFrame }));

function getHandler(type: string) {
  const call = useFrame.mock.calls.find((c) => c[0] === type);
  return call?.[1] as (frame: unknown) => void;
}

describe("RefreshHandler — notification frame", () => {
  it("prepends a new notification to the cached first page and bumps unread count", () => {
    useFrame.mockClear();
    const queryClient = new QueryClient();
    const key = queryKeys.notifications(false);
    queryClient.setQueryData(key, {
      pages: [{ items: [{ id: "existing", title: "Old", body: "", event_type: "x", source: "x", target_type: null, target_id: null, created_at: "2026-01-01T00:00:00Z", read: false }], next_cursor: null }],
      pageParams: [undefined],
    });
    queryClient.setQueryData(queryKeys.unreadNotificationCount, 2);

    render(
      <QueryClientProvider client={queryClient}>
        <RefreshHandler />
      </QueryClientProvider>,
    );

    const handler = getHandler("notification");
    handler({
      type: "notification",
      id: "new-1",
      event_type: "stuck_goal",
      source: "goals",
      title: "Goal stuck",
      body: "body",
      target_type: "goal",
      target_id: "goal-a",
      created_at: "2026-07-13T00:00:00Z",
      read: false,
    });

    const data = queryClient.getQueryData<{ pages: { items: { id: string }[] }[] }>(key);
    expect(data?.pages[0]?.items[0]?.id).toBe("new-1");
    expect(data?.pages[0]?.items).toHaveLength(2);
    expect(queryClient.getQueryData(queryKeys.unreadNotificationCount)).toBe(3);
  });

  it("no-ops when no notifications query is cached yet", () => {
    useFrame.mockClear();
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <RefreshHandler />
      </QueryClientProvider>,
    );

    const handler = getHandler("notification");
    expect(() =>
      handler({
        type: "notification",
        id: "new-1",
        event_type: "stuck_goal",
        source: "goals",
        title: "Goal stuck",
        body: "body",
        target_type: null,
        target_id: null,
        created_at: "2026-07-13T00:00:00Z",
        read: false,
      }),
    ).not.toThrow();
  });

  it("refetches open held writes when a held_write notification arrives", () => {
    useFrame.mockClear();
    const queryClient = new QueryClient();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    render(
      <QueryClientProvider client={queryClient}>
        <RefreshHandler />
      </QueryClientProvider>,
    );

    getHandler("notification")({
      type: "notification",
      id: "n-held",
      event_type: "write_approval_held",
      source: "workflow",
      title: "Workflow 'Weekly' needs your OK",
      body: "send an email",
      target_type: "held_write",
      target_id: "req-1",
      created_at: "2026-07-13T00:00:00Z",
      read: false,
    });

    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.heldWrites });
  });

  it("leaves held writes alone for other notifications", () => {
    useFrame.mockClear();
    const queryClient = new QueryClient();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    render(
      <QueryClientProvider client={queryClient}>
        <RefreshHandler />
      </QueryClientProvider>,
    );

    getHandler("notification")({
      type: "notification",
      id: "n-goal",
      event_type: "stuck_goal",
      source: "goals",
      title: "Goal stuck",
      body: "",
      target_type: "goal",
      target_id: "goal-a",
      created_at: "2026-07-13T00:00:00Z",
      read: false,
    });

    expect(invalidate).not.toHaveBeenCalledWith({ queryKey: queryKeys.heldWrites });
  });
});

describe("RefreshHandler - World keys", () => {
  function setup() {
    useFrame.mockClear();
    const queryClient = new QueryClient();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    render(
      <QueryClientProvider client={queryClient}>
        <RefreshHandler />
      </QueryClientProvider>,
    );
    const invalidated = () => invalidate.mock.calls.map((c) => c[0]?.queryKey);
    return { queryClient, invalidated, invalidate };
  }

  it("a message frame invalidates the World keys", () => {
    const { invalidated } = setup();
    getHandler("message")({ type: "message", message: { thread_id: "t" } });
    for (const key of [["loops"], ["priority-snapshot"], ["reminders"], ["hypotheses"], ["goals"], ["held-writes"], ["attention-budget"]]) {
      expect(invalidated()).toContainEqual(key);
    }
  });

  it("a notification frame also invalidates the budget, notifications-since and its target kind", () => {
    const { invalidated, invalidate } = setup();
    const frame = (target_type: string | null) => ({ type: "notification", id: "n", event_type: "x", source: "x", title: "t", body: "", target_type, target_id: "id", target_parent_id: null, created_at: "2026-10-17T00:00:00Z", push_class: "requested", urgency: "normal", delivery: "delivered" });
    getHandler("notification")(frame("open_loop"));
    expect(invalidated()).toContainEqual(["attention-budget"]);
    expect(invalidated()).toContainEqual(["notifications-since"]);
    expect(invalidated()).toContainEqual(["loops"]);
    invalidate.mockClear();
    getHandler("notification")(frame("goal_gate"));
    expect(invalidated()).toContainEqual(["goals"]);
    expect(invalidated()).toContainEqual(["priority-snapshot"]);
    invalidate.mockClear();
    getHandler("notification")(frame("workflow_execution"));
    expect(invalidated()).toContainEqual(["workflow-executions"]);
    invalidate.mockClear();
    getHandler("notification")(frame("reminder"));
    expect(invalidated()).toContainEqual(["reminders"]);
    invalidate.mockClear();
    getHandler("notification")(frame("hypothesis"));
    expect(invalidated()).toContainEqual(["hypotheses"]);
  });

  it("leaves a notifications-since cache untouched by the InfiniteData rewrite", () => {
    const { queryClient } = setup();
    const since = ["notifications-since", "2026-10-16T00:00:00Z"];
    queryClient.setQueryData(since, [{ id: "a" }]);
    getHandler("notification")({ type: "notification", id: "n", event_type: "x", source: "x", title: "t", body: "", target_type: null, target_id: null, target_parent_id: null, created_at: "x", push_class: "requested", urgency: "normal", delivery: "delivered" });
    expect(queryClient.getQueryData(since)).toEqual([{ id: "a" }]);
  });

  it("a goals refresh frame invalidates goals, the snapshot and workflow executions", () => {
    const { invalidated } = setup();
    getHandler("refresh")({ type: "refresh", screen: "goals" });
    expect(invalidated()).toEqual([["goals"], ["priority-snapshot"], ["workflow-executions"]]);
  });
});
