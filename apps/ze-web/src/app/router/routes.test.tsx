import { render, screen, waitFor } from "@testing-library/react";
import { Outlet, RouterProvider, createMemoryRouter, useLocation, useParams } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/widgets/app-shell", () => ({
  AppShell: ({ overlay }: { overlay?: React.ReactNode }) => (
    <div data-testid="shell">
      <Outlet />
      {overlay}
    </div>
  ),
}));
vi.mock("@/widgets/chat-workspace", () => ({ AskOverlay: () => <i data-testid="overlay" />, ChatWorkspace: () => null }));
vi.mock("@/pages/ask", () => ({
  AskInterim: () => {
    const { threadId } = useParams();
    return <p data-testid="ask">ask {threadId ?? "none"}</p>;
  },
}));
vi.mock("@/pages/world", () => ({ WorldInterim: () => <p data-testid="world">world</p> }));
vi.mock("@/pages/doing", () => ({ DoingInterim: ({ fallback }: { fallback: React.ReactNode }) => <p data-testid="doing">doing {fallback ? "" : ""}</p> }));
vi.mock("@/pages/mind", () => ({ MindInterim: () => <p data-testid="mind">mind</p> }));
vi.mock("@/pages/governance", () => ({
  GovernanceInterim: () => {
    const { hash, search } = useLocation();
    return <p data-testid="governance">governance {search}{hash}</p>;
  },
}));
vi.mock("@/pages/goal-detail", () => ({
  GoalDetailPage: () => <p data-testid="goal">goal {useParams().goalId}</p>,
}));
vi.mock("@/pages/workflow-detail", () => ({
  WorkflowDetailPage: () => <p data-testid="workflow">workflow {useParams().workflowId}</p>,
}));
vi.mock("@/pages/jarvis", () => ({ JarvisApp: () => <p data-testid="jarvis">jarvis</p> }));
vi.mock("@/pages/plugin-page", () => ({
  PluginPage: () => <p data-testid="plugin">plugin {useParams().pluginPath}</p>,
}));
vi.mock("@/pages/loops", () => ({ LoopsPage: () => null }));
vi.mock("@/pages/priority", () => ({ PriorityPage: () => null }));

import { routes } from "./routes";

function go(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(<RouterProvider router={router} />);
  return router;
}

const where = (router: ReturnType<typeof go>) => {
  const { pathname, search, hash } = router.state.location;
  return `${pathname}${search}${hash}`;
};

describe("places", () => {
  it.each([
    ["/", "world"],
    ["/world/priority", "world"],
    ["/ask", "ask"],
    ["/doing", "doing"],
    ["/doing/goals", "doing"],
    ["/mind", "mind"],
    ["/mind/graph", "mind"],
    ["/governance", "governance"],
    ["/governance/settings", "governance"],
  ])("%s renders inside the shell", async (path, id) => {
    go(path);
    expect(await screen.findByTestId(id)).toBeInTheDocument();
    expect(screen.getByTestId("shell")).toContainElement(screen.getByTestId(id));
    expect(screen.getByTestId("overlay")).toBeInTheDocument();
  });

  it("passes the thread to Ask", async () => {
    go("/ask/t-9");
    expect(await screen.findByTestId("ask")).toHaveTextContent("ask t-9");
  });

  it("renders goal and workflow detail under Doing", async () => {
    go("/doing/goals/g-1");
    expect(await screen.findByTestId("goal")).toHaveTextContent("goal g-1");
    go("/doing/workflows/w-1");
    expect(await screen.findByTestId("workflow")).toHaveTextContent("workflow w-1");
  });

  it("renders /jarvis as a child of the shell", async () => {
    go("/jarvis");
    const el = await screen.findByTestId("jarvis");
    expect(screen.getAllByTestId("shell")[0]).toContainElement(el);
  });

  it("renders a manifest plugin path through PluginPage", async () => {
    go("/contacts");
    expect(await screen.findByTestId("plugin")).toHaveTextContent("plugin contacts");
  });

  it("renders a way back for a path nothing owns", async () => {
    go("/nowhere/at/all");
    expect(await screen.findByRole("link", { name: /Back to the world/ })).toHaveAttribute("href", "/");
    expect(screen.getByTestId("shell")).toBeInTheDocument();
  });
});

describe("redirects", () => {
  it.each([
    ["/loops", "/"],
    ["/priority", "/world/priority"],
    ["/goals", "/doing/goals"],
    ["/goals/g-1", "/doing/goals/g-1"],
    ["/workflows", "/doing/workflows"],
    ["/workflows/w-1", "/doing/workflows/w-1"],
    ["/skills", "/doing/skills"],
    ["/procedures", "/doing/procedures"],
    ["/workspace", "/doing/workspace"],
    ["/brain-memory", "/mind"],
    ["/brain-graph", "/mind/graph"],
    ["/costs", "/governance"],
    ["/data", "/governance/data"],
    ["/settings", "/governance/settings"],
  ])("%s lands on %s", async (from, to) => {
    const router = go(from);
    await waitFor(() => expect(where(router)).toBe(to));
  });

  it("keeps the query and the hash", async () => {
    const router = go("/settings?x=1#your-data");
    await waitFor(() => expect(where(router)).toBe("/governance/settings?x=1#your-data"));
    expect(await screen.findByTestId("governance")).toHaveTextContent("?x=1#your-data");
  });

  it("keeps params, query and hash together", async () => {
    const router = go("/workflows/w-1?execution=e-1#run");
    await waitFor(() => expect(where(router)).toBe("/doing/workflows/w-1?execution=e-1#run"));
  });
});
