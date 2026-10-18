import { lazy, Suspense, type ComponentType } from "react";
import { type RouteObject } from "react-router-dom";
import { AskPage } from "@/pages/ask";
import { DoingPage } from "@/pages/doing";
import { DoingGoalPage } from "@/pages/doing-goal";
import { DoingWorkflowPage } from "@/pages/doing-workflow";
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
      { path: "doing", element: <DoingPage /> },
      { path: "doing/goals/:goalId", element: <DoingGoalPage /> },
      { path: "doing/workflows/:workflowId", element: <DoingWorkflowPage /> },
      { path: "mind", element: <MindPage /> },
      { path: "mind/:entityId", element: <MindEntityPage /> },
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
