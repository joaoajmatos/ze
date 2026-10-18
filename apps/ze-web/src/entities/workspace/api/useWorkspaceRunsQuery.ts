import { listWorkspaceRuns } from "@myguyze/ze-client";
import type { WorkspaceRunResponse } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import { hasRunning } from "../lib/run-status";

export const RUN_POLL_MS = 5000;

/** The backend sends no `refresh` frame for the workspace, so a run started from chat is found by polling while one is running. */
export function useWorkspaceRunsQuery({ limit }: { limit: number }) {
  return useQuery<WorkspaceRunResponse[]>({
    queryKey: [...queryKeys.workspaceRuns(), limit],
    queryFn: async () => {
      const { data, error } = await listWorkspaceRuns({ query: { limit } });
      if (error) throw error;
      return data?.runs ?? [];
    },
    refetchInterval: (q) => (hasRunning(q.state.data) ? RUN_POLL_MS : false),
  });
}
