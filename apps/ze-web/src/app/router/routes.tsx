import { lazy, Suspense, type ComponentType } from "react";
import { type RouteObject } from "react-router-dom";
import { AskPage } from "@/pages/ask";
import { DoingInterim } from "@/pages/doing";
import { GovernancePage } from "@/pages/governance";
import { MindPage } from "@/pages/mind";
import { MindEntityPage } from "@/pages/mind-entity";
import { WorldPage } from "@/pages/world";
import { AppShell } from "@/widgets/app-shell";
import { AskOverlay } from "@/widgets/assemble";
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
const doingLoaders = {
  goals: () => import("@/pages/goals").then((m) => ({ default: m.GoalsPage })),
  workflows: () => import("@/pages/workflows").then((m) => ({ default: m.WorkflowsPage })),
  skills: () => import("@/pages/skills").then((m) => ({ default: m.SkillsPage })),
};

// Only a development build routes the gallery; the production build drops the branch and its fixtures.
const devRoutes: RouteObject[] = import.meta.env.DEV
  ? [
      {
        path: "dev/primitives",
        element: lazyPage(() => import("@/pages/dev-primitives").then((m) => ({ default: m.DevPrimitivesPage }))),
      },
    ]
  : [];

const notFound = <ZeErrorFallback error={new Error("Nothing lives at this address.")} />;

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell overlay={<AskOverlay />} />,
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, element: <WorldPage /> },
      { path: "ask", element: <AskPage /> },
      { path: "ask/:threadId", element: <AskPage /> },
      {
        path: "doing/goals/:goalId",
        element: lazyPage(() => import("@/pages/goal-detail").then((m) => ({ default: m.GoalDetailPage }))),
      },
      {
        path: "doing/workflows/:workflowId",
        element: lazyPage(() => import("@/pages/workflow-detail").then((m) => ({ default: m.WorkflowDetailPage }))),
      },
      { path: "doing/*", element: <DoingInterim loaders={doingLoaders} fallback={notFound} /> },
      { path: "mind", element: <MindPage /> },
      { path: "mind/:entityId", element: <MindEntityPage /> },
      { path: "governance", element: <GovernancePage /> },
      { path: "governance/*", element: notFound },
      {
        path: "jarvis/*",
        element: lazyPage(() => import("@/pages/jarvis").then((m) => ({ default: m.JarvisApp }))),
      },
      ...devRoutes,
      ...redirects.map((r) => ({ path: r.from.slice(1), element: <RedirectTo to={r.to} hint={r.hint} hintMap={r.hintMap} /> })),
      { path: ":pluginPath", element: lazyPage(() => import("@/pages/plugin-page").then((m) => ({ default: m.PluginPage }))) },
      { path: "*", element: notFound },
    ],
  },
];
