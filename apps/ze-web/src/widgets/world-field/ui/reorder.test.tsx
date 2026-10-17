import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Concern } from "@/shared/lib";
import { concern, day, NOW } from "../lib/fixtures";
import { WorldField } from "./WorldField";

const api = vi.hoisted(() => ({ submitPriorityOverride: vi.fn(), unpinPriorityOverride: vi.fn() }));
vi.mock("@myguyze/ze-client", async (orig) => ({ ...(await orig<typeof import("@myguyze/ze-client")>()), ...api }));

const items: Concern[] = [
  concern("a", { title: "Alpha", rank: 1, due: day(2), confidence: 0.9 }),
  concern("b", { title: "Bravo", rank: 2, due: day(3), confidence: 0.7 }),
  concern("c", { title: "Charlie", rank: 3, due: day(4), confidence: 0.5 }),
];

function setup(concerns = items, extra: { selected?: string | null; offline?: boolean } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <WorldField concerns={concerns} now={NOW} loading={false} error={false} narrow={false} offline={extra.offline ?? false} selected={extra.selected ?? null} onSelect={() => {}} />
    </QueryClientProvider>,
  );
}

const mark = (name: RegExp) => screen.getByRole("button", { name });

describe("reorder", () => {
  beforeEach(() => {
    api.submitPriorityOverride.mockReset();
    api.unpinPriorityOverride.mockReset();
    api.submitPriorityOverride.mockResolvedValue({ data: {} });
    api.unpinPriorityOverride.mockResolvedValue({ data: {} });
  });

  it("Space lifts, arrows move the drop point, Space drops: payload anchors the neighbour", async () => {
    setup();
    const alpha = mark(/Alpha/);
    alpha.focus();
    fireEvent.keyDown(alpha, { key: " " });
    expect(screen.getByRole("status").textContent).toContain("Lifted Alpha");
    fireEvent.keyDown(alpha, { key: "ArrowDown" });
    fireEvent.keyDown(alpha, { key: "ArrowDown" });
    expect(screen.getByRole("status").textContent).toContain("below Charlie");
    fireEvent.keyDown(alpha, { key: " " });
    await waitFor(() => expect(api.submitPriorityOverride).toHaveBeenCalled());
    expect(api.submitPriorityOverride).toHaveBeenCalledWith({
      body: { source_kind: "loop", source_id: "a", anchor_source_kind: "loop", anchor_source_id: "c", relation: "below", pinned: false },
    });
  });

  it("moving up anchors with relation above", async () => {
    setup();
    const charlie = mark(/Charlie/);
    fireEvent.keyDown(charlie, { key: " " });
    fireEvent.keyDown(charlie, { key: "ArrowUp" });
    fireEvent.keyDown(charlie, { key: " " });
    await waitFor(() => expect(api.submitPriorityOverride).toHaveBeenCalled());
    expect(api.submitPriorityOverride.mock.calls[0][0].body).toMatchObject({ source_id: "c", anchor_source_id: "b", relation: "above" });
  });

  it("Escape cancels and submits nothing", () => {
    setup();
    const alpha = mark(/Alpha/);
    fireEvent.keyDown(alpha, { key: " " });
    fireEvent.keyDown(alpha, { key: "ArrowDown" });
    fireEvent.keyDown(alpha, { key: "Escape" });
    fireEvent.keyDown(alpha, { key: " " });
    expect(api.submitPriorityOverride).not.toHaveBeenCalled();
    expect(screen.getByRole("status").textContent).toContain("Lifted Alpha");
  });

  it("dropping where it started submits nothing", () => {
    setup();
    const alpha = mark(/Alpha/);
    fireEvent.keyDown(alpha, { key: " " });
    fireEvent.keyDown(alpha, { key: " " });
    expect(api.submitPriorityOverride).not.toHaveBeenCalled();
  });

  it("dragging a mark onto another submits the move", async () => {
    setup();
    const alpha = mark(/Alpha/);
    fireEvent.pointerDown(alpha, { button: 0, clientX: 10, clientY: 10 });
    fireEvent.pointerMove(document, { clientX: 40, clientY: 40 });
    fireEvent.pointerEnter(mark(/Bravo/));
    fireEvent.pointerUp(document);
    await waitFor(() => expect(api.submitPriorityOverride).toHaveBeenCalled());
    expect(api.submitPriorityOverride.mock.calls[0][0].body).toMatchObject({ source_id: "a", anchor_source_id: "b", relation: "below" });
  });

  it("the pin toggle is carried into the payload", async () => {
    setup(items, { selected: "loop:a" });
    fireEvent.click(screen.getByLabelText(/Pin where I drop it/));
    const alpha = mark(/Alpha/);
    fireEvent.keyDown(alpha, { key: " " });
    fireEvent.keyDown(alpha, { key: "ArrowDown" });
    fireEvent.keyDown(alpha, { key: " " });
    await waitFor(() => expect(api.submitPriorityOverride).toHaveBeenCalled());
    expect(api.submitPriorityOverride.mock.calls[0][0].body.pinned).toBe(true);
  });

  it("unpin calls the mutation with the override id", async () => {
    const pinned = [{ ...items[0], pinned: true, overridden: true, computedRank: 3, override: { id: "ov-1", pinned: true, anchor_source_kind: "loop", anchor_source_id: "b", relation: "above", submitted_at: "" } } as Concern, items[1]];
    setup(pinned, { selected: "loop:a" });
    fireEvent.click(screen.getByRole("button", { name: "Unpin" }));
    await waitFor(() => expect(api.unpinPriorityOverride).toHaveBeenCalledWith({ path: { override_id: "ov-1" } }));
  });

  it("does not submit while offline", () => {
    setup(items, { offline: true });
    const alpha = mark(/Alpha/);
    fireEvent.keyDown(alpha, { key: " " });
    fireEvent.keyDown(alpha, { key: "ArrowDown" });
    fireEvent.keyDown(alpha, { key: " " });
    expect(api.submitPriorityOverride).not.toHaveBeenCalled();
  });

  it("shows why this order: computed versus displayed rank", () => {
    const moved = [{ ...items[0], overridden: true, computedRank: 3 } as Concern, items[1]];
    setup(moved, { selected: "loop:a" });
    const region = screen.getByRole("region", { name: /Readout: Alpha/ });
    expect(region.textContent).toContain("#1");
    expect(region.textContent).toContain("Ze computed #3");
  });
});

describe("Chat about this on the readout", () => {
  it.each([
    ["loop", { kind: "loop" as const, key: "loop:a" }],
    ["goal", { kind: "goal" as const, key: "goal:a" }],
    ["hypothesis", { kind: "hypothesis" as const, key: "hypothesis:a" }],
    ["reminder", { kind: "reminder" as const, key: "reminder:a", rank: null }],
  ])("%s", (kind, extra) => {
    const onChatAbout = vi.fn();
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <WorldField concerns={[concern("a", { title: "Thing", ...extra })]} now={NOW} loading={false} error={false} narrow={false} offline={false} selected={extra.key} onSelect={() => {}} onChatAbout={onChatAbout} />
      </QueryClientProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Chat about Thing" }));
    expect(onChatAbout.mock.calls[0][0]).toMatchObject({ kind, id: "a" });
  });

  it("offers none for a relationship, which no resolver owns", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <WorldField concerns={[concern("p", { title: "Ana", kind: "relationship", key: "relationship:p" })]} now={NOW} loading={false} error={false} narrow={false} offline={false} selected="relationship:p" onSelect={() => {}} onChatAbout={vi.fn()} />
      </QueryClientProvider>,
    );
    expect(screen.queryByRole("button", { name: /Chat about/ })).toBeNull();
  });
});

describe("reorder: pointer safety", () => {
  beforeEach(() => {
    api.submitPriorityOverride.mockReset().mockResolvedValue({ data: {} });
  });

  it("releasing over empty space moves nothing", () => {
    setup();
    fireEvent.pointerDown(mark(/Alpha/), { button: 0, clientX: 10, clientY: 10 });
    fireEvent.pointerMove(document, { clientX: 50, clientY: 50 });
    fireEvent.pointerEnter(mark(/Bravo/));
    fireEvent.pointerLeave(mark(/Bravo/));
    fireEvent.pointerUp(document);
    expect(api.submitPriorityOverride).not.toHaveBeenCalled();
  });

  it("a cancelled pointer ends the drag, and the next release elsewhere submits nothing", () => {
    setup();
    fireEvent.pointerDown(mark(/Alpha/), { button: 0, clientX: 10, clientY: 10 });
    fireEvent.pointerMove(document, { clientX: 50, clientY: 50 });
    fireEvent.pointerEnter(mark(/Bravo/));
    fireEvent.pointerCancel(document);
    fireEvent.pointerUp(document);
    expect(api.submitPriorityOverride).not.toHaveBeenCalled();
  });

  it("Escape cancels a pointer drag", () => {
    setup();
    fireEvent.pointerDown(mark(/Alpha/), { button: 0, clientX: 10, clientY: 10 });
    fireEvent.pointerMove(document, { clientX: 50, clientY: 50 });
    fireEvent.pointerEnter(mark(/Bravo/));
    fireEvent.keyDown(document, { key: "Escape" });
    fireEvent.pointerUp(document);
    expect(api.submitPriorityOverride).not.toHaveBeenCalled();
  });

  it("refuses to lift offline and says why", () => {
    setup(items, { offline: true });
    fireEvent.keyDown(mark(/Alpha/), { key: " " });
    expect(screen.getByRole("status").textContent).toContain("offline");
  });

  it("announces the move only after it succeeded, and the failure when it did not", async () => {
    api.submitPriorityOverride.mockResolvedValue({ error: { detail: "boom" } });
    setup();
    const alpha = mark(/Alpha/);
    fireEvent.keyDown(alpha, { key: " " });
    fireEvent.keyDown(alpha, { key: "ArrowDown" });
    fireEvent.keyDown(alpha, { key: " " });
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("Couldn't move Alpha"));
  });
});
