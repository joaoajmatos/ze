import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import { subjectKey } from "../model/select";
import type { ModuleSubject } from "../model/types";
import { fetchUiModule } from "./fetchUiModule";

export function useUiModuleQuery(moduleId: string, subject: ModuleSubject, options: { refetchInterval?: number | false } = {}) {
  return useQuery({
    queryKey: queryKeys.uiModule(moduleId, subjectKey(subject)),
    queryFn: () => fetchUiModule(moduleId, subject),
    staleTime: 30_000,
    retry: false,
    ...options,
  });
}
