import { listSkills } from "@myguyze/ze-client";
import type { SkillResponse, SkillSource, SkillStatus } from "@myguyze/ze-client";
import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function useSkillsQuery(status?: SkillStatus, source?: SkillSource) {
  return useQuery<SkillResponse[]>({
    queryKey: queryKeys.skills(status, source),
    queryFn: async () => {
      const { data, error } = await listSkills({ query: { status, source } });
      if (error) throw error;
      return data?.skills ?? [];
    },
  });
}
