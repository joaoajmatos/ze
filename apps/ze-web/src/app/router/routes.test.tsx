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
vi.mock("@/widgets/assemble", () => ({ AskOverlay: () => <i data-testid="overlay" /> }));
vi.mock("@/pages/ask", () => ({
  AskPage: () => {
    const { threadId } = useParams();
    return <p data-testid="ask">ask {threadId ?? "none"}</p>;
  },
}));
vi.mock("@/pages/world", () => ({ WorldPage: () => <p data-testid="world">world</p> }));
vi.mock("@/pages/doing", () => ({ DoingPage: () => <p data-testid="doing">doing</p> }));
vi.mock("@/pages/mind", () => ({ MindPage: () => <p data-testid="mind">mind</p> }));
vi.mock("@/pages/mind-entity", () => ({ MindEntityPage: () => <p data-testid="mind-entity">entity {useParams().entityId}</p> }));
vi.mock("@/pages/governance", () => ({
  GovernancePage: () => {
    const { hash, search } = useLocation();
    return <p data-testid="governance">governance {search}{hash}</p>;
  },
}));
vi.mock("@/pages/doing-goal", () => ({
  DoingGoalPage: () => <p data-testid="goal">goal {useParams().goalId}</p>,
}));
vi.mock("@/pages/doing-workflow", () => ({
  DoingWorkflowPage: () => <p data-testid="workflow">workflow {useParams().workflowId}</p>,
}));
vi.mock("@/pages/dev-primitives", () => ({ DevPrimitivesPage: () => <p data-testid="dev-primitives">gallery</p> }));
vi.mock("@/pages/jarvis", () => ({ JarvisApp: () => <p data-testid="jarvis">jarvis</p> }));

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
    ["/ask", "ask"],
    ["/doing", "doing"],
    ["/mind", "mind"],
    ["/mind/11111111-1111-4111-8111-111111111111", "mind-entity"],
    ["/governance", "governance"],
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

  it("has no top-level plugin route: an old plugin path is not found", async () => {
    go("/notes");
    expect(await screen.findByRole("link", { name: /Back to the world/ })).toHaveAttribute("href", "/");
    expect(screen.queryByTestId("plugin")).toBeNull();
  });

  it("/world/priority is gone: nothing owns it any more", async () => {
    go("/world/priority");
    expect(await screen.findByRole("link", { name: /Back to the world/ })).toHaveAttribute("href", "/");
    expect(screen.queryByTestId("world")).toBeNull();
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
    ["/priority", "/"],
    ["/reminders", "/"],
    ["/world", "/"],
    ["/goals", "/doing#goals"],
    ["/goals/g-1", "/doing/goals/g-1"],
    ["/workflows", "/doing#workflows"],
    ["/workflows/w-1", "/doing/workflows/w-1"],
    ["/skills", "/doing#skills"],
    ["/doing/goals", "/doing#goals"],
    ["/doing/workflows", "/doing#workflows"],
    ["/doing/skills", "/doing#skills"],
    ["/procedures", "/mind"],
    ["/doing/procedures", "/mind"],
    ["/contacts", "/mind"],
    ["/news", "/ask"],
    ["/mind/graph", "/mind"],
    ["/workspace", "/governance#files"],
    ["/doing/workspace", "/governance#files"],
    ["/brain-memory", "/mind"],
    ["/brain-graph", "/mind"],
    ["/costs", "/governance"],
    ["/data", "/governance#data"],
    ["/governance/data", "/governance#data"],
    ["/settings", "/governance#connections"],
    ["/governance/settings", "/governance#connections"],
  ])("%s lands on %s", async (from, to) => {
    const router = go(from);
    await waitFor(() => expect(where(router)).toBe(to));
  });

  it("keeps the query and maps a legacy hash to its module", async () => {
    const router = go("/settings?x=1#your-data");
    await waitFor(() => expect(where(router)).toBe("/governance?x=1#data"));
    expect(await screen.findByTestId("governance")).toHaveTextContent("?x=1#data");
  });

  it("sends other /governance paths to not found", async () => {
    go("/governance/nowhere");
    expect(await screen.findByText(/nothing lives at this address/i)).toBeInTheDocument();
    expect(screen.queryByTestId("governance")).toBeNull();
  });

  it("keeps params, query and hash together", async () => {
    const router = go("/workflows/w-1?execution=e-1#run");
    await waitFor(() => expect(where(router)).toBe("/doing/workflows/w-1?execution=e-1#run"));
  });
});

describe("dev primitives gallery", () => {
  async function routesWith(dev: boolean) {
    vi.stubEnv("DEV", dev);
    vi.resetModules();
    return (await import("./routes")).routes;
  }

  it("is routed in development", async () => {
    const router = createMemoryRouter(await routesWith(true), { initialEntries: ["/dev/primitives"] });
    render(<RouterProvider router={router} />);
    expect(await screen.findByTestId("dev-primitives")).toBeInTheDocument();
    vi.unstubAllEnvs();
  });

  it("is not routed in production", async () => {
    const router = createMemoryRouter(await routesWith(false), { initialEntries: ["/dev/primitives"] });
    render(<RouterProvider router={router} />);
    expect(await screen.findByRole("link", { name: /Back to the world/ })).toBeInTheDocument();
    expect(screen.queryByTestId("dev-primitives")).toBeNull();
    vi.unstubAllEnvs();
  });
});
