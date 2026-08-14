import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import type { WorkspaceRunItem } from "./types";
import { workspaceFetch } from "./workspaceFetch";

export function useWorkspaceRunsQuery(origin?: string) {
  return useQuery<WorkspaceRunItem[]>({
    queryKey: queryKeys.workspaceRuns(origin),
    queryFn: async () => {
      const qs = origin ? `?origin=${encodeURIComponent(origin)}` : "";
      const res = await workspaceFetch(`/workspace/runs${qs}`);
      const data = (await res.json()) as { runs: WorkspaceRunItem[] };
      return data.runs ?? [];
    },
  });
}
