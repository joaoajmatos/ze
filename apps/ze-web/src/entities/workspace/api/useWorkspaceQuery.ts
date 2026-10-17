import { getWorkspace } from "@myguyze/ze-client";
import type { WorkspaceRunResponse } from "@myguyze/ze-client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import { hasRunning } from "../lib/run-status";
import { RUN_POLL_MS } from "./useWorkspaceRunsQuery";
import type { WorkspaceStatus } from "./types";

export function useWorkspaceQuery(enabled = true) {
  const queryClient = useQueryClient();
  return useQuery<WorkspaceStatus>({
    queryKey: queryKeys.workspace(),
    queryFn: async () => {
      const { data, error } = await getWorkspace();
      if (error) throw error;
      return data!;
    },
    enabled,
    refetchInterval: () => {
      const runs = queryClient.getQueriesData<WorkspaceRunResponse[]>({ queryKey: queryKeys.workspaceRuns() });
      return runs.some(([, d]) => hasRunning(d)) ? RUN_POLL_MS : false;
    },
  });
}
