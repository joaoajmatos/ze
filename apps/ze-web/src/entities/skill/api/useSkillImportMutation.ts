import { importSkill } from "@myguyze/ze-client";
import type { SkillDetailResponse } from "@myguyze/ze-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export function useSkillImportMutation() {
  const queryClient = useQueryClient();

  return useMutation<SkillDetailResponse, Error, { url: string }>({
    mutationFn: async ({ url }) => {
      const { data, error } = await importSkill({ body: { url } });
      if (error) throw error;
      return data!;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.skills() });
    },
  });
}
