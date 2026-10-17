import type { NotificationListResponse } from "@myguyze/ze-client";
import type { InfiniteData } from "@tanstack/react-query";
import { useQueryClient } from "@tanstack/react-query";
import type { UiManifest } from "@/entities/ui-manifest";
import { useFrame } from "@/shared/api";
import { queryKeys, refreshKeysForScreen } from "@/shared/lib";

const WORLD_KEYS: readonly (readonly string[])[] = [
  queryKeys.loopsAll,
  queryKeys.prioritySnapshot(),
  queryKeys.remindersAll,
  queryKeys.hypothesesAll,
  queryKeys.goals,
  queryKeys.heldWrites,
  queryKeys.attentionBudget,
];

/** What a notification about a record means for the World queries. */
const TARGET_KEYS: Record<string, readonly (readonly string[])[]> = {
  open_loop: [queryKeys.loopsAll],
  goal: [queryKeys.goals, queryKeys.prioritySnapshot()],
  goal_gate: [queryKeys.goals, queryKeys.prioritySnapshot()],
  workflow_execution: [queryKeys.workflowExecutionsAll],
  reminder: [queryKeys.remindersAll],
  hypothesis: [queryKeys.hypothesesAll],
};

export function RefreshHandler() {
  const queryClient = useQueryClient();

  useFrame("refresh", (frame) => {
    const manifest = queryClient.getQueryData<UiManifest>(queryKeys.uiManifest);
    const keys = refreshKeysForScreen(frame.screen, manifest);
    for (const key of keys ?? []) void queryClient.invalidateQueries({ queryKey: [...key] });
  });

  // Loops are written after a turn with no `refresh` frame, so a reply is the cue to re-read the World keys.
  useFrame("message", () => {
    for (const key of WORLD_KEYS) void queryClient.invalidateQueries({ queryKey: [...key] });
  });

  useFrame("notification", (frame) => {
    if (frame.target_type === "held_write") {
      void queryClient.invalidateQueries({ queryKey: queryKeys.heldWrites });
    }
    queryClient.setQueriesData<InfiniteData<NotificationListResponse>>(
      { queryKey: ["notifications"] },
      (data) => {
        if (!data) return data;
        const [firstPage, ...rest] = data.pages;
        const item = {
          id: frame.id,
          event_type: frame.event_type,
          source: frame.source,
          title: frame.title,
          body: frame.body,
          target_type: frame.target_type,
          target_id: frame.target_id,
          target_parent_id: frame.target_parent_id,
          created_at: frame.created_at,
          read: false,
          push_class: frame.push_class,
          urgency: frame.urgency,
          delivery: frame.delivery,
          // Unknown until the list refetches; a released push's delivery time is not its creation time.
          delivered_at: null,
        };
        const updatedFirstPage: NotificationListResponse = firstPage
          ? { ...firstPage, items: [item, ...firstPage.items] }
          : { items: [item], next_cursor: null };
        return { ...data, pages: [updatedFirstPage, ...rest] };
      },
    );

    void queryClient.invalidateQueries({ queryKey: queryKeys.attentionBudget });
    void queryClient.invalidateQueries({ queryKey: queryKeys.notificationsSinceAll });
    for (const key of TARGET_KEYS[frame.target_type ?? ""] ?? []) void queryClient.invalidateQueries({ queryKey: [...key] });
    queryClient.setQueryData<number>(
      queryKeys.unreadNotificationCount,
      (count) => (count ?? 0) + 1,
    );
  });

  return null;
}
