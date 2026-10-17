import { listProactiveJobRuns } from "@myguyze/ze-client";
import type { ProactiveJobRunItem } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";
import { jobLabel } from "../lib/job-labels";

export type VisibleJobRun = ProactiveJobRunItem & { label: string };

export function useProactiveJobRunsQuery(since: string) {
  return useQuery<VisibleJobRun[]>({
    queryKey: queryKeys.proactiveJobRuns(since),
    queryFn: async () => {
      const { data, error } = await listProactiveJobRuns({ query: { since } });
      if (error) throw error;
      const runs: VisibleJobRun[] = [];
      for (const run of data ?? []) {
        const label = jobLabel(run.job_id);
        if (label) runs.push({ ...run, label });
      }
      return runs;
    },
  });
}
