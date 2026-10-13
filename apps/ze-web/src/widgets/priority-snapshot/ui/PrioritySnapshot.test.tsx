import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PrioritySnapshot } from "./PrioritySnapshot";

const {
  usePrioritySnapshotQuery,
  useReprioritizeMutation,
  useUnpinPriorityOverrideMutation,
} = vi.hoisted(() => ({
  usePrioritySnapshotQuery: vi.fn(),
  useReprioritizeMutation: vi.fn(),
  useUnpinPriorityOverrideMutation: vi.fn(),
}));

vi.mock("@/entities/priority-item", () => ({
  usePrioritySnapshotQuery,
  useReprioritizeMutation,
  useUnpinPriorityOverrideMutation,
}));

const loopItem = {
  source_kind: "loop",
  source_id: "id-1",
  title: "Follow up with Maria",
  displayed_rank: 1,
  computed_rank: 1,
  overridden_from_computed: false,
  override: null,
};

function setup(items: unknown[], sourcesFailed: string[]) {
  usePrioritySnapshotQuery.mockReturnValue({
    data: { items, sourcesFailed },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  });
  useReprioritizeMutation.mockReturnValue({ mutate: vi.fn(), isPending: false });
  useUnpinPriorityOverrideMutation.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  });
}

describe("PrioritySnapshot", () => {
  it("shows a notice naming the source that could not be loaded", () => {
    setup([loopItem], ["goal"]);
    render(<PrioritySnapshot />);

    expect(screen.getByText(/Couldn't load: Goal/)).toBeInTheDocument();
  });

  it("shows no notice when every source loaded", () => {
    setup([loopItem], []);
    render(<PrioritySnapshot />);

    expect(screen.queryByText(/Couldn't load/)).not.toBeInTheDocument();
  });

  it("labels a relationship item", () => {
    setup(
      [{ ...loopItem, source_kind: "relationship", source_id: "id-2", title: "Ana" }],
      [],
    );
    render(<PrioritySnapshot />);

    expect(screen.getByText("Relationship")).toBeInTheDocument();
  });
});
