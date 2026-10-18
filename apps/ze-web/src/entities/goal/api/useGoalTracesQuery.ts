import { listGoalTraces } from "@myguyze/ze-client";
import type { ExecutionTraceResponse } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export const TRACE_LIMIT = 100;

export function useGoalTracesQuery(goalId: string, milestoneId?: string) {
  return useQuery<ExecutionTraceResponse[]>({
    queryKey: queryKeys.goalTraces(goalId, milestoneId),
    queryFn: async () => {
      const { data, error } = await listGoalTraces({
        path: { goal_id: goalId },
        query: { limit: TRACE_LIMIT, ...(milestoneId ? { milestone_id: milestoneId } : {}) },
      });
      if (error) throw error;
      return data ?? [];
    },
    enabled: !!goalId,
  });
}
