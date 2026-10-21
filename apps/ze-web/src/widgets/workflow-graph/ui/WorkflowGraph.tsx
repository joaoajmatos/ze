import type { WorkflowStepResponse, WorkflowExecutionResponse } from "@myguyze/ze-client";
import { ReactFlow, ReactFlowProvider, Background, useReactFlow, type Node, type Edge } from "@xyflow/react";
import { useMemo, useState } from "react";
import "@xyflow/react/dist/style.css";
import { buildWorkflowGraph } from "@/entities/workflow";
import { layoutGraph, nodeSize } from "../lib/layout";
import { StepDetailPanel } from "./StepDetailPanel";
import { StepNode, type StepNodeData } from "./StepNode";
import { WorkflowGraphToolbar } from "./WorkflowGraphToolbar";

const nodeTypes = { step: StepNode };

interface Props {
  steps: WorkflowStepResponse[];
  execution?: WorkflowExecutionResponse | null;
  isLive?: boolean;
}

function WorkflowGraphInner({ steps, execution }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hideNotTaken, setHideNotTaken] = useState(false);
  const { fitView } = useReactFlow();

  const graph = useMemo(() => buildWorkflowGraph(steps, execution ?? null), [steps, execution]);

  const { nodes, edges } = useMemo(() => {
    const visibleNodes = hideNotTaken ? graph.nodes.filter((n) => n.state !== "not-taken") : graph.nodes;
    const visibleIds = new Set(visibleNodes.map((n) => n.id));

    const rfNodes: Node<StepNodeData>[] = visibleNodes.map((graphNode) => ({
      id: graphNode.id,
      type: "step",
      position: { x: 0, y: 0 },
      data: { graphNode, selected: graphNode.id === selectedId },
      draggable: false,
      ...nodeSize(graphNode.step.task),
    }));

    const rfEdges: Edge[] = graph.edges
      .filter((e) => visibleIds.has(e.from) && visibleIds.has(e.to))
      .map((e) => ({
        id: e.id,
        source: e.from,
        target: e.to,
        label: e.label ?? undefined,
        animated: e.taken && execution?.status === "running",
        style: {
          stroke: e.taken ? "var(--main)" : "var(--hair-strong)",
          strokeWidth: e.taken ? 2 : 1,
        },
        labelStyle: { fill: e.taken ? "var(--cream)" : "var(--dim)", fontSize: 11 },
        labelBgStyle: { fill: "var(--field)" },
      }));

    return { nodes: layoutGraph(rfNodes, rfEdges), edges: rfEdges };
  }, [graph, hideNotTaken, selectedId, execution?.status]);

  const selectedNode = selectedId ? (graph.nodes.find((n) => n.id === selectedId) ?? null) : null;

  if (!steps.length) {
    return <p className="muted">No steps defined.</p>;
  }

  return (
    <div className="graph-wrap">
      <div className="graph-main">
        <div className="graph-toolbar">
          <WorkflowGraphToolbar
            hideNotTaken={hideNotTaken}
            onToggleHideNotTaken={() => setHideNotTaken((v) => !v)}
            onFitView={() => fitView({ padding: 0.2, duration: 300 })}
          />
        </div>
        <div className="graph-frame">
        <ReactFlow
          key={execution?.id ?? "current"}
          fitView
          fitViewOptions={{ padding: 0.2, duration: 0 }}
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={(_, node) => setSelectedId((prev) => (prev === node.id ? null : node.id))}
          onPaneClick={() => setSelectedId(null)}
          nodesDraggable={false}
          nodesConnectable={false}
          minZoom={0.2}
          maxZoom={1.5}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="color-mix(in oklab, var(--main) 10%, transparent)" gap={24} />
        </ReactFlow>
        </div>
      </div>

      {selectedNode && (
        <div className="graph-detail">
          <StepDetailPanel
            node={selectedNode}
            executionError={execution?.error ?? null}
            onClose={() => setSelectedId(null)}
          />
        </div>
      )}
    </div>
  );
}

export function WorkflowGraph(props: Props) {
  return (
    <ReactFlowProvider>
      <WorkflowGraphInner {...props} />
    </ReactFlowProvider>
  );
}
