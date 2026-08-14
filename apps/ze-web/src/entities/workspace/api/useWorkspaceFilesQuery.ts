import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import type { WorkspaceFileItem } from "./types";
import { workspaceFetch } from "./workspaceFetch";

export function useWorkspaceFilesQuery(path = "") {
  return useQuery<WorkspaceFileItem[]>({
    queryKey: queryKeys.workspaceFiles(path),
    queryFn: async () => {
      const qs = path ? `?path=${encodeURIComponent(path)}` : "";
      const res = await workspaceFetch(`/workspace/files${qs}`);
      const data = (await res.json()) as { files: WorkspaceFileItem[] };
      return data.files ?? [];
    },
  });
}
