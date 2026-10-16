import { listWorkspaceFiles } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import type { WorkspaceFileItem } from "./types";

export function useWorkspaceFilesQuery(path = "") {
  return useQuery<WorkspaceFileItem[]>({
    queryKey: queryKeys.workspaceFiles(path),
    queryFn: async () => {
      const { data, error } = await listWorkspaceFiles({ query: path ? { path } : {} });
      if (error) throw error;
      return data?.files ?? [];
    },
  });
}
