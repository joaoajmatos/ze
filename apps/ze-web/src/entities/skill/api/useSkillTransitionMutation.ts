import {
  approveSkill,
  rejectSkill,
  disableSkill,
  enableSkill,
  deleteSkill,
  ApiError,
} from "@myguyze/ze-client";
import type { SkillDetailResponse } from "@myguyze/ze-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { getConfig } from "@/shared/config";
import { queryKeys } from "@/shared/lib";

export type SkillTransitionKind =
  | "approve"
  | "reject"
  | "disable"
  | "enable"
  | "remove"
  | "approve-executables";

const TRANSITION_FN = {
  approve: approveSkill,
  reject: rejectSkill,
  disable: disableSkill,
  enable: enableSkill,
} as const;

async function approveSkillExecutables(skillId: string): Promise<SkillDetailResponse> {
  const cfg = getConfig();
  if (!cfg) throw new ApiError(401, "Not configured");
  const res = await fetch(
    `${cfg.serverUrl.replace(/\/$/, "")}/api/v0/skills/${skillId}/approve-executables`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${cfg.apiKey}` },
    },
  );
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json() as Promise<SkillDetailResponse>;
}

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
      if (kind === "approve-executables") {
        return approveSkillExecutables(skillId);
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
