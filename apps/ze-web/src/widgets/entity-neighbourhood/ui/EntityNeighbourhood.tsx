import type { EntityDetailResponse, GraphEntityNode, WsScreenRef } from "@myguyze/ze-client";
import { LineChart } from "@myguyze/ze-ui/charts";
import { useMemo, type KeyboardEvent } from "react";
import { BeliefRow, factRef, useReviewFactMutation } from "@/entities/memory-feed-item";
import { humanizeIdentifier, useNarrow } from "@/shared/lib";
import { ChatAboutChip, Module } from "@/shared/ui";
import { entityActivitySeries } from "../lib/entityActivitySeries";
import { factAsFeedItem } from "../lib/facts";
import { radialLayout } from "../lib/radial";

const FILTERS = { type: "all" } as const;

interface EntityNeighbourhoodProps {
  detail: EntityDetailResponse;
  onSelectEntity: (entityId: string) => void;
  onChatAbout?: (ref: WsScreenRef, element: Element) => void;
}

export const entityRef = (e: GraphEntityNode): WsScreenRef => ({ kind: "entity", id: e.id, label: e.canonical_name, component: "entity_module" });

const words = (predicate: string) => humanizeIdentifier(predicate);

export function EntityNeighbourhood({ detail, onSelectEntity, onChatAbout }: EntityNeighbourhoodProps) {
  const narrow = useNarrow();
  const review = useReviewFactMutation(FILTERS);
  const name = detail.entity.canonical_name;
  const layout = useMemo(
    () => radialLayout(detail.entity, detail.neighbours, detail.neighbour_edges, detail.neighbour_total),
    [detail],
  );
  const activity = useMemo(() => entityActivitySeries(detail), [detail]);
  const open = (id: string) => (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelectEntity(id);
    }
  };

  return (
    <Module
      label={`Around ${name}`}
      onChatAbout={onChatAbout ? (element) => onChatAbout(entityRef(detail.entity), element) : undefined}
      chatAboutLabel={name}
    >
      {layout.shown === 0 ? (
        <p className="note">Nothing connected to {name} yet.</p>
      ) : narrow ? (
        <div className="hood-list">
          {layout.groups.map((g) => (
            <div key={g.predicate} role="group" aria-label={words(g.predicate)}>
              <h3 className="lbl">{words(g.predicate)}</h3>
              <ul>
                {g.nodes.map(({ node }) => (
                  <li key={node.id}>
                    <button type="button" className="ctl-text hood-link" onClick={() => onSelectEntity(node.id)}>
                      {node.canonical_name}
                    </button>
                    {onChatAbout && (
                      <ChatAboutChip label={node.canonical_name} onClick={(chip) => onChatAbout(entityRef(node), chip.closest("li") ?? chip)} />
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      ) : (
        <svg
          className="hood-field"
          viewBox={`0 0 ${layout.size} ${layout.size}`}
          role="img"
          aria-label={`${name} and ${layout.shown} neighbours`}
        >
          {layout.groups.flatMap((g) =>
            g.nodes.map((n) => (
              <line key={`l-${n.node.id}`} x1={layout.centre.x} y1={layout.centre.y} x2={n.x} y2={n.y} className="hood-edge" aria-hidden="true" />
            )),
          )}
          <circle cx={layout.centre.x} cy={layout.centre.y} r={7} className="hood-centre" />
          <text x={layout.centre.x} y={layout.centre.y + 24} textAnchor="middle" className="hood-label hood-label-centre">{name}</text>
          {layout.groups.flatMap((g) =>
            g.nodes.map((n) => (
              <g
                key={n.node.id}
                role="link"
                tabIndex={0}
                aria-label={`Open ${n.node.canonical_name}, ${words(g.predicate).toLowerCase()}`}
                className="hood-node"
                onClick={() => onSelectEntity(n.node.id)}
                onKeyDown={(e) => {
                  if (e.key === "c" && onChatAbout && !e.metaKey && !e.ctrlKey && !e.altKey) {
                    e.preventDefault();
                    onChatAbout(entityRef(n.node), e.currentTarget);
                    return;
                  }
                  open(n.node.id)(e);
                }}              >
                <circle cx={n.x} cy={n.y} r={14} className="hood-hit" />
                <circle cx={n.x} cy={n.y} r={4} className="hood-dot" />
                <text x={n.labelX} y={n.labelY} textAnchor={n.anchor} className="hood-label">{n.node.canonical_name}</text>
              </g>
            )),
          )}
        </svg>
      )}
      {layout.more > 0 && <p className="note">+{layout.more} more</p>}

      {activity.length > 0 && (
        <LineChart
          data={activity}
          seriesLabels={{ fact: "Facts", episode: "Episodes" }}
          title="Activity over time, last 20 facts and 10 episodes"
          yLabel="items"
        />
      )}

      {detail.facts.length > 0 && (
        <ul className="belief-list">
          {detail.facts.map((f) => (
            <BeliefRow
              key={f.id}
              item={factAsFeedItem(f)}
              busy={review.isPending}
              onChatAbout={onChatAbout ? (element) => onChatAbout(factRef(f), element) : undefined}
              onKeep={() => review.mutate({ actions: [{ id: f.id, action: "confirm" }] })}
              onDrop={() => review.mutate({ actions: [{ id: f.id, action: "reject" }] })}
              onEdit={(value) => review.mutate({ actions: [{ id: f.id, action: "edit", value }] })}
            />
          ))}
        </ul>
      )}
    </Module>
  );
}
