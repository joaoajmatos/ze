import { useState, type FocusEvent } from "react";
import { DoingNeedsYou } from "@/widgets/doing-needs-you";
import { GoalsBoard } from "@/widgets/goals-board";
import { Runs } from "@/widgets/runs";
import { SkillsQueue } from "@/widgets/skills-queue";
import { WorkflowsBoard } from "@/widgets/workflows-board";
import { useAnswerGate } from "@/features/answer-gate";
import { useChatAbout } from "@/features/ask-bar";
import { useHeldWritesQuery } from "@/entities/confirmation";
import { useGoalsQuery } from "@/entities/goal";
import { useScreenPublisher } from "@/entities/screen-context";
import { useSkillsQuery } from "@/entities/skill";
import { useLatestExecutionsQuery, useWorkflowsQuery } from "@/entities/workflow";
import { useWorkspaceQuery, useWorkspaceRunsQuery } from "@/entities/workspace";
import { useWsStore } from "@/shared/api";
import { RedirectHintTarget } from "@/shared/ui";

/** Doing: what runs without you, what it did, what waits for you. DOM order is the phone order. */
export function DoingPage() {
  const goals = useGoalsQuery();
  const held = useHeldWritesQuery();
  const workflows = useWorkflowsQuery();
  const skills = useSkillsQuery();
  const runs = useWorkspaceRunsQuery({ limit: 20 });
  const workspace = useWorkspaceQuery();
  const chatAbout = useChatAbout();
  const offline = !useWsStore((s) => s.isConnected);
  const now = new Date();
  const [focused, setFocused] = useState<string | null>(null);

  const workflowList = workflows.data ?? [];
  const latest = useLatestExecutionsQuery(workflowList.map((w) => w.id));
  const goalList = goals.data ?? [];

  // One sender for the page: its flights end when the id leaves this list.
  const gate = useAnswerGate([...goalList.filter((g) => g.gate_id).map((g) => g.gate_id!), ...goalList.filter((g) => g.stuck_since).map((g) => g.id)]);

  useScreenPublisher({
    visible: [
      ...goalList.slice(0, 10).map((g) => ({ kind: "goal", id: g.id, label: g.title })),
      ...workflowList.slice(0, 10).map((w) => ({ kind: "workflow", id: w.id, label: w.name })),
      ...(runs.data ?? []).filter((r) => r.id).slice(0, 5).map((r) => ({ kind: "workspace_run", id: r.id!, label: r.command })),
    ] as never,
    ...(focused ? { focused_module: focused } : {}),
  });

  function onFocus(e: FocusEvent<HTMLElement>) {
    const name = (e.target as HTMLElement).closest("[data-module]")?.getAttribute("data-module");
    if (name) setFocused(name);
  }

  return (
    <div className="doing-grid" onFocusCapture={onFocus}>
      <div className="doing-col">
        <div data-module="Needs you">
          <DoingNeedsYou goals={goalList} held={held.data ?? []} loading={goals.isLoading || held.isLoading} error={goals.isError || held.isError} now={now} offline={offline} gate={gate} onChatAbout={chatAbout} />
        </div>
        <RedirectHintTarget hintId="goals" data-module="Goals">
          <GoalsBoard goals={goalList} loading={goals.isLoading} error={goals.isError} offline={offline} gate={gate} onChatAbout={chatAbout} />
        </RedirectHintTarget>
      </div>
      <div className="doing-col">
        <RedirectHintTarget hintId="workflows" data-module="Workflows">
          <WorkflowsBoard workflows={workflowList} executions={latest.byWorkflow} loading={workflows.isLoading || latest.loading} error={workflows.isError || latest.error} offline={offline} now={now} onChatAbout={chatAbout} />
        </RedirectHintTarget>
        <RedirectHintTarget hintId="runs" data-module="Runs">
          <Runs runs={runs.data ?? []} loading={runs.isLoading || workspace.isLoading} error={runs.isError} workspace={workspace.data} workspaceError={workspace.isError} now={now} onChatAbout={chatAbout} />
        </RedirectHintTarget>
      </div>
      <div className="doing-col">
        <RedirectHintTarget hintId="skills" data-module="Skills">
          <SkillsQueue skills={skills.data ?? []} loading={skills.isLoading} error={skills.isError} onChatAbout={chatAbout} />
        </RedirectHintTarget>
      </div>
    </div>
  );
}
