import { getUiModule } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import { subjectKey } from "../model/select";
import type { ModuleSubject } from "../model/types";

/** The plain line the server sent for a failed module, or a generic one. */
function detailOf(error: unknown): string {
  const detail = (error as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" ? detail : "This module could not load.";
}

export function useUiModuleQuery(moduleId: string, subject: ModuleSubject, options: { refetchInterval?: number | false } = {}) {
  return useQuery({
    queryKey: queryKeys.uiModule(moduleId, subjectKey(subject)),
    queryFn: async () => {
      const { data, error } = await getUiModule({
        path: { module_id: moduleId },
        query: { subject_kind: subject.kind, subject_id: subject.id, parent_id: subject.parent_id },
      });
      if (error || !data) throw new Error(detailOf(error));
      return data;
    },
    staleTime: 30_000,
    retry: false,
    ...options,
  });
}
