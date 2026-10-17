import type { GraphEntityNode } from "@myguyze/ze-client";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EntitySearch } from "./EntitySearch";

const { useSearchEntitiesQuery } = vi.hoisted(() => ({ useSearchEntitiesQuery: vi.fn() }));
vi.mock("@/entities/memory-graph", () => ({ useSearchEntitiesQuery }));

const ada: GraphEntityNode = { id: "e1", entity_type: "person", canonical_name: "Ada Lovelace", aliases: [], attrs: {}, degree: 4 };

describe("EntitySearch", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useSearchEntitiesQuery.mockReturnValue({ data: undefined, isFetching: false, isError: false });
  });
  afterEach(() => vi.useRealTimers());

  it("waits 250 ms before it searches", () => {
    render(<EntitySearch onSelect={vi.fn()} />);
    fireEvent.change(screen.getByRole("searchbox", { name: /search entities/i }), { target: { value: "ada" } });
    expect(useSearchEntitiesQuery).toHaveBeenLastCalledWith("", undefined);
    act(() => void vi.advanceTimersByTime(250));
    expect(useSearchEntitiesQuery).toHaveBeenLastCalledWith("ada", undefined);
  });

  it("lists results with type, name and degree, and selects one", () => {
    const onSelect = vi.fn();
    useSearchEntitiesQuery.mockReturnValue({ data: [ada], isFetching: false, isError: false });
    render(<EntitySearch onSelect={onSelect} />);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "ada" } });
    act(() => void vi.advanceTimersByTime(250));
    const row = screen.getByRole("button", { name: /ada lovelace/i });
    expect(row).toHaveTextContent("person");
    expect(row).toHaveTextContent("4");
    fireEvent.click(row);
    expect(onSelect).toHaveBeenCalledWith("e1");
  });

  it("says no entity was found and keeps the text", () => {
    useSearchEntitiesQuery.mockReturnValue({ data: [], isFetching: false, isError: false });
    render(<EntitySearch onSelect={vi.fn()} />);
    const box = screen.getByRole("searchbox") as HTMLInputElement;
    fireEvent.change(box, { target: { value: "zzz" } });
    act(() => void vi.advanceTimersByTime(250));
    expect(screen.getByText("No entity named zzz")).toBeInTheDocument();
    expect(box.value).toBe("zzz");
  });

  it("invites a search before anything is typed", () => {
    render(<EntitySearch onSelect={vi.fn()} />);
    expect(screen.getByText(/search for a person, place or project/i)).toBeInTheDocument();
  });
});
