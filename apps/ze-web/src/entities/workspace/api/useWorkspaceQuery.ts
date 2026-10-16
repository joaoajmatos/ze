import { getWorkspace } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import type { WorkspaceStatus } from "./types";

export function useWorkspaceQuery(enabled = true) {
  return useQuery<WorkspaceStatus>({
    queryKey: queryKeys.workspace(),
    queryFn: async () => {
      const { data, error } = await getWorkspace();
      if (error) throw error;
      return data!;
    },
    enabled,
  });
}
