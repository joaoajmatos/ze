import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import button from "../../../../../../packages/ze-ui/fixtures/button.json";
import legacy from "../../../../../../packages/ze-ui/fixtures/legacy-stored-tree.json";
import { ConnectedPrimitiveTree } from "./ConnectedPrimitiveTree";

const tree = (subject: string, ref_id = "r1") => [
  { type: "claim_card", title: "Ana Costa", claim: { subject, ref_id } },
];

function renderTree(components: unknown, onChatAbout?: (ref: unknown, el: Element) => void, uiVersion?: string) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <ConnectedPrimitiveTree components={components} onChatAbout={onChatAbout} uiVersion={uiVersion} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ConnectedPrimitiveTree chat about", () => {
  it("shows no chip without the prop", () => {
    renderTree(tree("loop"));
    expect(screen.queryByRole("button", { name: /Chat about/ })).toBeNull();
  });

  it("maps a claim to a screen ref", () => {
    const onChatAbout = vi.fn();
    renderTree(tree("loop", "L1"), onChatAbout);
    fireEvent.click(screen.getByRole("button", { name: "Chat about Ana Costa" }));
    expect(onChatAbout).toHaveBeenCalledWith(
      { kind: "loop", id: "L1", label: "Ana Costa", component: "claim_card" },
      expect.any(HTMLElement),
    );
  });

  it("a person claim has no chip: its ref id is derived from the name, not a contact id", () => {
    renderTree(tree("person", "p1"), vi.fn());
    expect(screen.queryByRole("button", { name: /Chat about/ })).toBeNull();
  });
});

describe("ConnectedPrimitiveTree HUD restyle", () => {
  it("passes the HUD classes and draws a headline in dot matrix", () => {
    renderTree([
      { type: "headline", text: "3 slipping" },
      { type: "text", content: "Total", style: "label" },
      { type: "badge", label: "ok" },
    ]);
    expect(screen.getByRole("img", { name: "3 slipping" })).toBeInTheDocument();
    expect(screen.getByText("Total")).toHaveClass("pr-label");
    expect(screen.getByText("ok")).toHaveClass("pr-badge");
  });
});

describe("ConnectedPrimitiveTree versions", () => {
  it("renders a shared fixture under ui_version 2.0", () => {
    renderTree(button, undefined, "2.0");
    expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled();
  });

  it("renders a stored pre-191a tree in legacy mode: its buttons stay visible but cannot run", () => {
    renderTree(legacy);
    expect(screen.getByText("Delete this?")).toBeInTheDocument();
    const yes = screen.getByRole("button", { name: "Yes" });
    expect(yes).toBeDisabled();
    expect(yes).toHaveAttribute("title", "This older button no longer works.");
  });

  it("replaces only a legacy tree that cannot be parsed", () => {
    renderTree([{ type: "col" }]);
    expect(screen.getByText("This older view can't be shown.")).toBeInTheDocument();
  });

  it("says so when a current tree is invalid instead of drawing nothing", () => {
    renderTree([{ type: "col" }], undefined, "2.0");
    expect(screen.getByText("This view can't be shown.")).toBeInTheDocument();
  });
});
