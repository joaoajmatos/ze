import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { memo } from "react";
import type { StepState, WorkflowGraphNode } from "@/entities/workflow";

export interface StepNodeData extends Record<string, unknown> {
  graphNode: WorkflowGraphNode;
  selected: boolean;
}

export type StepNodeType = Node<StepNodeData, "step">;

export const STEP_STATE_WORD: Record<StepState, string> = {
  "completed-ok": "done",
  "completed-fail": "failed",
  "failed-inferred": "failed",
  running: "running",
  pending: "waiting",
  "not-taken": "not taken this run",
};

function StepNodeInner({ data }: NodeProps<StepNodeType>) {
  const { graphNode, selected } = data;
  const { step, state } = graphNode;
  return (
    <div className={`step-node ${state} ${selected ? "selected" : ""}`} role="button" aria-label={`${step.task}: ${STEP_STATE_WORD[state]}`}>
      <Handle type="target" position={Position.Top} className="step-handle" />
      <span className="step-mark" aria-hidden="true" />
      <p className="step-task">{step.task}</p>
      {state === "not-taken" && <p className="step-note">Not taken this run</p>}
      <Handle type="source" position={Position.Bottom} className="step-handle" />
    </div>
  );
}

export const StepNode = memo(StepNodeInner);
