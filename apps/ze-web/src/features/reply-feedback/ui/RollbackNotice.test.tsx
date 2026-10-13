import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { RollbackRecordResponse } from "@myguyze/ze-client";
import { RollbackNotice } from "./RollbackNotice";

function record(
  state: RollbackRecordResponse["state"],
  outcomes: Array<["undone" | "failed" | "not_attempted", string]>,
): RollbackRecordResponse {
  return {
    state,
    replaced_by: null,
    entries: outcomes.map(([outcome, effect_phrase], i) => ({
      entry_id: `e${i}`,
      tool: "t",
      effect_phrase,
      outcome,
    })),
  };
}

describe("RollbackNotice", () => {
  it("explains a partial rollback", () => {
    render(
      <RollbackNotice
        rollback={record("partial", [
          ["undone", "set a reminder"],
          ["failed", "created a goal"],
        ])}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Ze undid set a reminder, but could not undo created a goal.",
    );
  });

  it("explains a failed regeneration after a full undo", () => {
    render(
      <RollbackNotice rollback={record("rolled_back_retry_failed", [["undone", "set a reminder"]])} />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Ze undid set a reminder but could not write a new reply.",
    );
  });

  it("explains a retry waiting on confirmation", () => {
    render(
      <RollbackNotice
        rollback={record("rolled_back_awaiting_confirmation", [
          ["undone", "set a reminder"],
          ["undone", "created a goal"],
        ])}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "Ze undid set a reminder and created a goal and is waiting for your confirmation.",
    );
  });

  it("renders nothing without a record or once superseded", () => {
    const { rerender } = render(<RollbackNotice rollback={null} />);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    rerender(<RollbackNotice rollback={record("superseded", [["undone", "x"]])} />);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
