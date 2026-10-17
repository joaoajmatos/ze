import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/widgets/chat-workspace", () => ({
  ChatWorkspace: ({ threadId }: { threadId?: string }) => <p data-testid="chat">{threadId ?? "default"}</p>,
}));

import { useSession } from "@/entities/session";
import { AskInterim } from "./AskInterim";

beforeEach(() => useSession.setState({ threadId: "t-old" }));

function at(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/ask" element={<AskInterim />} />
        <Route path="/ask/:threadId" element={<AskInterim />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("AskInterim", () => {
  it("renders the chat on the selected thread at /ask", () => {
    at("/ask");
    expect(screen.getByTestId("chat")).toHaveTextContent("default");
    expect(useSession.getState().threadId).toBe("t-old");
  });

  it("opens and selects the thread from the URL", () => {
    at("/ask/t-9");
    expect(screen.getByTestId("chat")).toHaveTextContent("t-9");
    expect(useSession.getState().threadId).toBe("t-9");
  });
});
