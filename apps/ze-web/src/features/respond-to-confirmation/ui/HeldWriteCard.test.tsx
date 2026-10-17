import type { HeldWriteOut } from "@myguyze/ze-client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HeldWriteCard } from "./HeldWriteCard";

const { decideHeldWrite } = vi.hoisted(() => ({ decideHeldWrite: vi.fn() }));
vi.mock("@myguyze/ze-client", async (orig) => ({ ...(await orig<typeof import("@myguyze/ze-client")>()), decideHeldWrite }));

const plain = {
  request_id: "req-1",
  source: "workflow",
  source_name: "Weekly summary",
  owner_ref: "wf-1",
  status: "open",
  items: [{ item_id: "i1", effect_phrase: "Send the weekly summary to Ana", summary: "Email, 2 attachments" }],
} as unknown as HeldWriteOut;

const editable = {
  ...plain,
  request_id: "req-2",
  items: [{ item_id: "i1", effect_phrase: "Send a reply", summary: "To Ana", editable_field: "body", proposed_text: "Hi Ana" }],
} as unknown as HeldWriteOut;

function setup(held: HeldWriteOut, props: { disabled?: boolean } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <HeldWriteCard held={held} {...props} />
    </QueryClientProvider>,
  );
}

describe("HeldWriteCard", () => {
  beforeEach(() => {
    decideHeldWrite.mockReset();
    decideHeldWrite.mockResolvedValue({ data: { status: "approved" } });
  });

  it("names the source and the effect", () => {
    setup(plain);
    expect(screen.getByText(/Weekly summary/)).toBeTruthy();
    expect(screen.getByText("Send the weekly summary to Ana")).toBeTruthy();
  });

  it("approve and deny call the mutation with the request id", async () => {
    setup(plain);
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(decideHeldWrite).toHaveBeenCalledWith({ path: { request_id: "req-1" }, body: { choice: "approve", edits: {} } }));
    fireEvent.click(screen.getByRole("button", { name: "Deny" }));
    await waitFor(() => expect(decideHeldWrite).toHaveBeenLastCalledWith({ path: { request_id: "req-1" }, body: { choice: "deny", edits: {} } }));
  });

  it("an editable item opens the confirmation card and sends the edit", async () => {
    setup(editable);
    fireEvent.change(screen.getByLabelText("Edit body"), { target: { value: "Hi Ana, Friday works" } });
    fireEvent.click(screen.getByRole("button", { name: "Approve all" }));
    await waitFor(() => expect(decideHeldWrite).toHaveBeenCalled());
    expect(decideHeldWrite).toHaveBeenCalledWith({ path: { request_id: "req-2" }, body: { choice: "approve", edits: { i1: "Hi Ana, Friday works" } } });
  });

  it("is disabled while that request is pending, and when told to be", async () => {
    let resolve: (v: unknown) => void = () => {};
    decideHeldWrite.mockReturnValue(new Promise((r) => (resolve = r)));
    setup(plain);
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect((screen.getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(true));
    expect((screen.getByRole("button", { name: "Deny" }) as HTMLButtonElement).disabled).toBe(true);
    resolve({ data: {} });
  });

  it("disabled prop disables the actions", () => {
    setup(plain, { disabled: true });
    expect((screen.getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows the error line when the decision fails", async () => {
    decideHeldWrite.mockResolvedValue({ error: { detail: "x" } });
    setup(plain);
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});
