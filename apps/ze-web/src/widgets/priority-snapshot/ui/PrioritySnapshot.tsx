import {
  DndContext,
  type DragEndEvent,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import type { PrioritySnapshotItem } from "@myguyze/ze-client";
import { ListTodo, Pin, PinOff } from "lucide-react";
import { useState } from "react";
import {
  usePrioritySnapshotQuery,
  useReprioritizeMutation,
  useUnpinPriorityOverrideMutation,
} from "@/entities/priority-item";
import { Button, ListPage } from "@/shared/ui";

const SOURCE_LABEL: Record<string, string> = {
  loop: "Loop",
  goal: "Goal",
  hypothesis: "Hypothesis",
};

function SourceBadge({ sourceKind }: { sourceKind: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-foreground/10 px-2 py-0.5 text-xs font-medium">
      {SOURCE_LABEL[sourceKind] ?? sourceKind}
    </span>
  );
}

function PriorityRow({
  item,
  onPin,
  onUnpin,
  pinPending,
  unpinPending,
}: {
  item: PrioritySnapshotItem;
  onPin: (item: PrioritySnapshotItem) => void;
  onUnpin: (overrideId: string) => void;
  pinPending: boolean;
  unpinPending: boolean;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: item.source_id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="flex items-center justify-between gap-4 rounded-lg border border-foreground/10 bg-background px-4 py-3"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-xs text-smoke">#{item.displayed_rank}</span>
          <SourceBadge sourceKind={item.source_kind} />
          <span className="truncate text-sm font-medium">{item.title}</span>
          {item.overridden_from_computed && (
            <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-xs text-amber-500">
              Ze would rank this differently
            </span>
          )}
        </div>
      </div>
      {item.override && (
        <Button
          size="sm"
          variant="ghost"
          disabled={item.override.pinned ? unpinPending : pinPending}
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation();
            if (item.override!.pinned) {
              onUnpin(item.override!.id);
            } else {
              onPin(item);
            }
          }}
        >
          {item.override.pinned ? (
            <>
              <PinOff className="mr-1 size-3.5" /> Unpin
            </>
          ) : (
            <>
              <Pin className="mr-1 size-3.5" /> Pin
            </>
          )}
        </Button>
      )}
    </div>
  );
}

export function PrioritySnapshot() {
  const { data: items, isLoading, isError, refetch } = usePrioritySnapshotQuery();
  const reprioritize = useReprioritizeMutation();
  const unpin = useUnpinPriorityOverrideMutation();
  const [error, setError] = useState<string | null>(null);

  const sensors = useSensors(useSensor(PointerSensor));
  const ordered = [...(items ?? [])].sort((a, b) => a.displayed_rank - b.displayed_rank);

  function handlePin(item: PrioritySnapshotItem) {
    if (!item.override) return;
    setError(null);
    reprioritize.mutate(
      {
        source_kind: item.source_kind,
        source_id: item.source_id,
        anchor_source_kind: item.override.anchor_source_kind,
        anchor_source_id: item.override.anchor_source_id,
        relation: item.override.relation,
        pinned: true,
      },
      {
        onError: () => setError("Could not pin that item — please try again."),
      },
    );
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const activeItem = ordered.find((i) => i.source_id === active.id);
    const overItem = ordered.find((i) => i.source_id === over.id);
    if (!activeItem || !overItem) return;

    setError(null);
    reprioritize.mutate(
      {
        source_kind: activeItem.source_kind,
        source_id: activeItem.source_id,
        anchor_source_kind: overItem.source_kind,
        anchor_source_id: overItem.source_id,
        relation: "above",
        pinned: false,
      },
      {
        onError: () => setError("Could not save that reorder — please try again."),
      },
    );
  }

  return (
    <ListPage
      isLoading={isLoading}
      isError={isError}
      isEmpty={!ordered.length}
      emptyIcon={ListTodo}
      emptyMessage="Nothing is currently open to prioritize."
      errorMessage="Could not load the priority snapshot."
      onRetry={() => void refetch()}
    >
      {error && <p className="mb-2 text-sm text-red-500">{error}</p>}
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext
          items={ordered.map((i) => i.source_id)}
          strategy={verticalListSortingStrategy}
        >
          <div className="space-y-2">
            {ordered.map((item) => (
              <PriorityRow
                key={item.source_id}
                item={item}
                pinPending={reprioritize.isPending}
                unpinPending={unpin.isPending}
                onPin={handlePin}
                onUnpin={(overrideId) => unpin.mutate({ overrideId })}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </ListPage>
  );
}
