import { useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import { placeWorkspaceFile, type PlacedWorkspaceFile } from "./placeWorkspaceFile";

export function useWorkspaceUploadMutation() {
  const queryClient = useQueryClient();
  return useMutation<PlacedWorkspaceFile, Error, File>({
    mutationFn: (file) => placeWorkspaceFile(file),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.workspaceFiles() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.workspace() });
    },
  });
}
