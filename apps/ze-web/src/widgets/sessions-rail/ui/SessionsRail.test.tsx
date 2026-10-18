import type { SessionSchema } from "@myguyze/ze-client";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSession } from "@/entities/session";
import { useWsStore } from "@/shared/api";
import { SessionsRail } from "./SessionsRail";

const session = (id: string, title: string): SessionSchema => ({
  id, title, preview: null, title_source: "generated", created_at: "2026-10-17T10:00:00Z", last_active_at: "2026-10-17T10:00:00Z",
}) as SessionSchema;

let browse: { items: SessionSchema[] } = { items: [] };
let browseState = { isLoading: false, isError: false };
let searchResults: unknown[] = [];
const searchSpy = vi.fn();

vi.mock("@/entities/session", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/entities/session")>()),
  useSessionsQuery: () => ({ data: { pages: [browse] }, hasNextPage: false, isFetchingNextPage: false, fetchNextPage: vi.fn(), ...browseState }),
  useSessionSearchQuery: (q: string) => {
    searchSpy(q);
    return { data: q.trim().length >= 2 ? searchResults : undefined, isLoading: false, isError: false };
  },
}));

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal("IntersectionObserver", class { observe() {} disconnect() {} });
  browse = { items: [session("s1", "Trip planning"), session("s2", "Tax questions")] };
  browseState = { isLoading: false, isError: false };
  searchResults = [];
  useSession.setState({ threadId: "s1" });
  useWsStore.setState({ thinkingThreads: {}, attentionThreads: {} });
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("SessionsRail", () => {
  it("lists sessions and marks the active one", () => {
    render(<SessionsRail />);
    expect(screen.getByText("Trip planning")).toBeTruthy();
    expect(screen.getByText("Tax questions")).toBeTruthy();
  });

  it("rows are 44px buttons", () => {
    render(<SessionsRail />);
    expect(screen.getByRole("button", { name: "Tax questions" }).style.minHeight).toBe("44px");
  });

  it("select sets the session", () => {
    render(<SessionsRail />);
    fireEvent.click(screen.getByText("Tax questions"));
    expect(useSession.getState().threadId).toBe("s2");
  });

  it("New chat starts a fresh thread", () => {
    render(<SessionsRail />);
    fireEvent.click(screen.getByRole("button", { name: "New chat" }));
    expect(useSession.getState().threadId).not.toBe("s1");
    expect(useSession.getState().threadId).toMatch(/^ze-/);
  });

  it("shows thinking and attention dots with text names", () => {
    useWsStore.setState({ thinkingThreads: { s2: true }, attentionThreads: { s1: true } });
    render(<SessionsRail />);
    expect(screen.getByLabelText("Tax questions is replying")).toBeTruthy();
    expect(screen.getByLabelText("Trip planning has a new reply")).toBeTruthy();
  });

  it("searches after a debounce and shows the results", () => {
    searchResults = [{ ...session("s9", "Visa renewal"), snippet: "…<b>visa</b>…", match_source: "message" }];
    render(<SessionsRail />);
    fireEvent.change(screen.getByLabelText("Search conversations"), { target: { value: "visa" } });
    expect(screen.queryByText("Visa renewal")).toBeNull();
    act(() => void vi.advanceTimersByTime(300));
    expect(screen.getByText("Visa renewal")).toBeTruthy();
    expect(screen.getByText("…visa…")).toBeTruthy();
    expect(screen.queryByText("Trip planning")).toBeNull();
  });

  it("says so when a search finds nothing and when there are no sessions", () => {
    browse = { items: [] };
    const { unmount } = render(<SessionsRail />);
    expect(screen.getByText("No past sessions yet.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Search conversations"), { target: { value: "zzz" } });
    act(() => void vi.advanceTimersByTime(300));
    expect(screen.getByText("No conversations found.")).toBeTruthy();
    unmount();
  });

  it("reports a failed read instead of an empty list", () => {
    browse = { items: [] };
    browseState = { isLoading: false, isError: true };
    render(<SessionsRail />);
    expect(screen.getByRole("alert").textContent).toContain("Couldn't read your conversations");
    expect(screen.queryByText("No past sessions yet.")).toBeNull();
  });
});
