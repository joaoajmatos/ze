import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { NotificationBell } from "./NotificationBell";

const {
  useNotificationsQuery,
  useUnreadCountQuery,
  useMarkReadMutation,
  useMarkAllReadMutation,
  useHeldWritesQuery,
  useDecideHeldWriteMutation,
} = vi.hoisted(() => ({
  useNotificationsQuery: vi.fn(),
  useUnreadCountQuery: vi.fn(),
  useMarkReadMutation: vi.fn(),
  useMarkAllReadMutation: vi.fn(),
  useHeldWritesQuery: vi.fn(),
  useDecideHeldWriteMutation: vi.fn(),
}));

vi.mock("@/entities/confirmation", () => ({
  useHeldWritesQuery,
  useDecideHeldWriteMutation,
}));

vi.mock("@/entities/notification", () => ({
  useNotificationsQuery,
  useUnreadCountQuery,
  useMarkReadMutation,
  useMarkAllReadMutation,
}));

function renderBell(initialEntry = "/") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <NotificationBell />
      <LocationProbe />
    </MemoryRouter>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname + location.search}</span>;
}

const heldWrite = {
  request_id: "req-1",
  source: "workflow" as const,
  source_name: "Weekly summary",
  owner_ref: "wf-1",
  status: "open" as const,
  items: [
    {
      item_id: "c1",
      agent: "messenger",
      tool: "send_email",
      effect_phrase: "send an email",
      summary: "To Ana — Weekly summary",
      conflict: null,
      editable_field: "body",
      proposed_text: "Hi Ana",
    },
  ],
};

function setHeld(held: (typeof heldWrite)[] = [], mutate = vi.fn()) {
  useHeldWritesQuery.mockReturnValue({ data: held });
  useDecideHeldWriteMutation.mockReturnValue({ mutate, isPending: false, variables: undefined });
  return mutate;
}

const item = {
  id: "notif-1",
  event_type: "stuck_goal",
  source: "goals",
  title: "Goal stuck",
  body: "Goal A hasn't moved in 3 days",
  target_type: "goal",
  target_id: "goal-a",
  created_at: new Date().toISOString(),
  read: false,
  push_class: "accountability",
  delivery: "delivered",
};

function setup({
  unreadCount = 0,
  items = [] as (typeof item)[],
}: { unreadCount?: number; items?: (typeof item)[] } = {}) {
  useUnreadCountQuery.mockReturnValue({ data: unreadCount });
  useNotificationsQuery.mockReturnValue({
    data: { pages: [{ items, next_cursor: null }] },
    isLoading: false,
    fetchNextPage: vi.fn(),
    hasNextPage: false,
    isFetchingNextPage: false,
  });
  useMarkReadMutation.mockReturnValue({ mutate: vi.fn() });
  useMarkAllReadMutation.mockReturnValue({ mutate: vi.fn() });
  setHeld();
}

describe("NotificationBell", () => {
  it("shows the unread count badge", () => {
    setup({ unreadCount: 3 });
    renderBell();

    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("hides the badge when unread count is zero", () => {
    setup({ unreadCount: 0 });
    renderBell();

    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("shows the empty state when there are no notifications", () => {
    setup({ items: [] });
    renderBell();

    fireEvent.click(screen.getByLabelText("Notifications"));

    expect(screen.getByText("You're all caught up.")).toBeInTheDocument();
  });

  it("renders notification items when the panel is open", () => {
    setup({ items: [item] });
    renderBell();

    fireEvent.click(screen.getByLabelText("Notifications"));

    expect(screen.getByText("Goal stuck")).toBeInTheDocument();
    expect(screen.getByText("Goal A hasn't moved in 3 days")).toBeInTheDocument();
  });

  it("calls mark-all-read when the action is clicked", () => {
    const mutate = vi.fn();
    setup({ unreadCount: 2, items: [item] });
    useMarkAllReadMutation.mockReturnValue({ mutate });
    renderBell();

    fireEvent.click(screen.getByLabelText("Notifications"));
    fireEvent.click(screen.getByText("Mark all read"));

    expect(mutate).toHaveBeenCalled();
  });

  it("marks an unread item read on click", () => {
    const mutate = vi.fn();
    setup({ items: [item] });
    useMarkReadMutation.mockReturnValue({ mutate });
    renderBell();

    fireEvent.click(screen.getByLabelText("Notifications"));
    fireEvent.click(screen.getByText("Goal stuck"));

    expect(mutate).toHaveBeenCalledWith("notif-1");
  });

  it("renders a targetless confirmation_request row and opens nothing on click", () => {
    const mutate = vi.fn();
    setup({
      items: [
        {
          ...item,
          id: "n-confirm",
          event_type: "confirmation_request",
          source: "conversation",
          title: "Ze needs your approval",
          body: "abandon a goal",
          target_type: null as unknown as string,
          target_id: null as unknown as string,
        },
      ],
    });
    useMarkReadMutation.mockReturnValue({ mutate });
    renderBell("/chat");

    fireEvent.click(screen.getByLabelText("Notifications"));
    fireEvent.click(screen.getByText("Ze needs your approval"));

    expect(mutate).toHaveBeenCalledWith("n-confirm");
    expect(screen.getByTestId("location")).toHaveTextContent("/chat");
    expect(screen.getByText("abandon a goal")).toBeInTheDocument();
  });

  it("labels a held item", () => {
    setup({ items: [{ ...item, delivery: "held" }] });
    renderBell();

    fireEvent.click(screen.getByLabelText("Notifications"));

    expect(screen.getByText("Held for quiet hours")).toBeInTheDocument();
  });

  it("labels a suppressed item", () => {
    setup({ items: [{ ...item, delivery: "suppressed" }] });
    renderBell();

    fireEvent.click(screen.getByLabelText("Notifications"));

    expect(screen.getByText("Not pushed: daily limit")).toBeInTheDocument();
  });

  it("shows no label for an ordinary delivery", () => {
    setup({ items: [item] });
    renderBell();

    fireEvent.click(screen.getByLabelText("Notifications"));

    expect(screen.queryByText("Held for quiet hours")).not.toBeInTheDocument();
    expect(screen.queryByText("Not pushed: daily limit")).not.toBeInTheDocument();
  });

  describe("held writes", () => {
    it("shows nothing extra when no write is held", () => {
      setup({ items: [item] });
      renderBell();
      fireEvent.click(screen.getByLabelText("Notifications"));
      expect(screen.queryByText(/waiting for your OK/i)).not.toBeInTheDocument();
    });

    it("lists each open held write as a confirmation card with its source", () => {
      setup({ items: [] });
      setHeld([heldWrite]);
      renderBell();
      fireEvent.click(screen.getByLabelText("Notifications"));
      expect(screen.getByText("send an email")).toBeInTheDocument();
      expect(screen.getByText(/workflow: Weekly summary/i)).toBeInTheDocument();
      expect(screen.queryByText("You're all caught up.")).not.toBeInTheDocument();
    });

    it("approves with only the edited text", () => {
      setup();
      const mutate = setHeld([heldWrite]);
      renderBell();
      fireEvent.click(screen.getByLabelText("Notifications"));
      fireEvent.change(screen.getByRole("textbox"), { target: { value: "Hello Ana" } });
      fireEvent.click(screen.getByRole("button", { name: "Approve all" }));
      expect(mutate).toHaveBeenCalledWith({
        requestId: "req-1",
        choice: "approve",
        edits: { c1: "Hello Ana" },
      });
    });

    it("denies a held write", () => {
      setup();
      const mutate = setHeld([heldWrite]);
      renderBell();
      fireEvent.click(screen.getByLabelText("Notifications"));
      fireEvent.click(screen.getByRole("button", { name: "Deny all" }));
      expect(mutate).toHaveBeenCalledWith({ requestId: "req-1", choice: "deny", edits: {} });
    });

    it("opens the panel and highlights the card named by ?confirm=", () => {
      setup();
      setHeld([heldWrite]);
      renderBell("/?confirm=req-1");
      expect(screen.getByTestId("held-write-req-1")).toHaveAttribute("data-highlighted", "true");
    });

    it("leaves the panel closed when ?confirm= matches no held write", () => {
      setup();
      setHeld([heldWrite]);
      renderBell("/?confirm=other");
      expect(screen.queryByTestId("held-write-req-1")).not.toBeInTheDocument();
    });

    it("clears ?confirm= once the write is answered", () => {
      setup();
      setHeld([heldWrite]);
      renderBell("/chat?confirm=req-1");
      fireEvent.click(screen.getByRole("button", { name: "Deny all" }));
      expect(screen.getByTestId("location")).toHaveTextContent("/chat");
      expect(screen.getByTestId("location")).not.toHaveTextContent("confirm=");
    });

    it("deep-links a held_write notification to its card", () => {
      setup({
        items: [{ ...item, id: "n2", target_type: "held_write", target_id: "req-1", title: "Approve?" }],
      });
      setHeld([heldWrite]);
      renderBell("/goals");
      fireEvent.click(screen.getByLabelText("Notifications"));
      fireEvent.click(screen.getByText("Approve?"));
      expect(screen.getByTestId("location")).toHaveTextContent("/goals?confirm=req-1");
      expect(screen.getByTestId("held-write-req-1")).toHaveAttribute("data-highlighted", "true");
    });
  });
});
