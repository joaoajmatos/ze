import {
  approveSkill,
  rejectSkill,
  disableSkill,
  enableSkill,
  deleteSkill,
} from "@myguyze/ze-client";
import type { SkillDetailResponse } from "@myguyze/ze-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/shared/lib";

export type SkillTransitionKind = "approve" | "reject" | "disable" | "enable" | "remove";

const TRANSITION_FN = {
  approve: approveSkill,
  reject: rejectSkill,
  disable: disableSkill,
  enable: enableSkill,
} as const;

export function useSkillTransitionMutation() {
  const queryClient = useQueryClient();

  return useMutation<
    SkillDetailResponse | undefined,
    Error,
    { skillId: string; kind: SkillTransitionKind }
  >({
    mutationFn: async ({ skillId, kind }) => {
      if (kind === "remove") {
        const { error } = await deleteSkill({ path: { skill_id: skillId } });
        if (error) throw error;
        return undefined;
      }
      const { data, error } = await TRANSITION_FN[kind]({ path: { skill_id: skillId } });
      if (error) throw error;
      return data!;
    },
    onSuccess: (_data, { skillId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.skills() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.skillDetail(skillId) });
    },
  });
}
