import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import type { WorkspaceStatus } from "./types";
import { workspaceFetch } from "./workspaceFetch";

export function useWorkspaceQuery(enabled = true) {
  return useQuery<WorkspaceStatus>({
    queryKey: queryKeys.workspace(),
    queryFn: async () => {
      const res = await workspaceFetch("/workspace");
      return res.json() as Promise<WorkspaceStatus>;
    },
    enabled,
  });
}
