import { lazy, Suspense, type ComponentType } from "react";
import { type RouteObject } from "react-router-dom";
import { AskInterim } from "@/pages/ask";
import { DoingInterim } from "@/pages/doing";
import { GovernancePage } from "@/pages/governance";
import { MindInterim } from "@/pages/mind";
import { WorldInterim } from "@/pages/world";
import { AppShell } from "@/widgets/app-shell";
import { AskOverlay } from "@/widgets/chat-workspace";
import { redirects } from "@/shared/config";
import { ZeErrorFallback } from "@/shared/ui";
import { RedirectTo } from "./RedirectTo";
import { RouteErrorPage } from "./RouteErrorPage";

function lazyPage(loader: () => Promise<{ default: ComponentType }>) {
  const Lazy = lazy(loader);
  return (
    <Suspense fallback={<div className="interim-loading lbl">Loading</div>}>
      <Lazy />
    </Suspense>
  );
}

// Interim sections load the old pages; they live here because a page cannot import a page.
const worldLoaders = {
  loops: () => import("@/pages/loops").then((m) => ({ default: m.LoopsPage })),
  priority: () => import("@/pages/priority").then((m) => ({ default: m.PriorityPage })),
};
const doingLoaders = {
  goals: () => import("@/pages/goals").then((m) => ({ default: m.GoalsPage })),
  workflows: () => import("@/pages/workflows").then((m) => ({ default: m.WorkflowsPage })),
  skills: () => import("@/pages/skills").then((m) => ({ default: m.SkillsPage })),
  procedures: () => import("@/pages/procedures").then((m) => ({ default: m.ProceduresPage })),
};
const mindLoaders = {
  memory: () => import("@/pages/brain-memory").then((m) => ({ default: m.BrainMemoryPage })),
  graph: () => import("@/pages/brain-graph").then((m) => ({ default: m.BrainGraphPage })),
};

const notFound = <ZeErrorFallback error={new Error("Nothing lives at this address.")} />;

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell overlay={<AskOverlay />} />,
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, element: <WorldInterim loaders={worldLoaders} /> },
      { path: "world/*", element: <WorldInterim loaders={worldLoaders} fallback={notFound} /> },
      { path: "ask", element: <AskInterim /> },
      { path: "ask/:threadId", element: <AskInterim /> },
      {
        path: "doing/goals/:goalId",
        element: lazyPage(() => import("@/pages/goal-detail").then((m) => ({ default: m.GoalDetailPage }))),
      },
      {
        path: "doing/workflows/:workflowId",
        element: lazyPage(() => import("@/pages/workflow-detail").then((m) => ({ default: m.WorkflowDetailPage }))),
      },
      { path: "doing/*", element: <DoingInterim loaders={doingLoaders} fallback={notFound} /> },
      { path: "mind/*", element: <MindInterim loaders={mindLoaders} fallback={notFound} /> },
      { path: "governance", element: <GovernancePage /> },
      { path: "governance/*", element: notFound },
      {
        path: "jarvis/*",
        element: lazyPage(() => import("@/pages/jarvis").then((m) => ({ default: m.JarvisApp }))),
      },
      ...redirects.map((r) => ({ path: r.from.slice(1), element: <RedirectTo to={r.to} hint={r.hint} hintMap={r.hintMap} /> })),
      { path: ":pluginPath", element: lazyPage(() => import("@/pages/plugin-page").then((m) => ({ default: m.PluginPage }))) },
      { path: "*", element: notFound },
    ],
  },
];
