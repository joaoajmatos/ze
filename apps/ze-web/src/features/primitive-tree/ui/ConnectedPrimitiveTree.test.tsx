import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ConnectedPrimitiveTree } from "./ConnectedPrimitiveTree";

const tree = (subject: string, ref_id = "r1") => [
  { type: "claim_card", title: "Ana Costa", claim: { subject, ref_id } },
];

function renderTree(components: unknown, onChatAbout?: (ref: unknown, el: Element) => void) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <ConnectedPrimitiveTree components={components} onChatAbout={onChatAbout} />
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
