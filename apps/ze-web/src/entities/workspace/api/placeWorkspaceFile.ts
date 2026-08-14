import { ApiError } from "@myguyze/ze-client";
import { getConfig } from "@/shared/config";

export interface PlacedWorkspaceFile {
  path: string;
  requested_path: string;
  size: number;
  deduplicated: boolean;
}

export async function placeWorkspaceFile(file: File, dest?: string): Promise<PlacedWorkspaceFile> {
  const cfg = getConfig();
  if (!cfg) throw new ApiError(401, "Not configured");
  const form = new FormData();
  form.append("file", file);
  if (dest) form.append("path", dest);
  const res = await fetch(`${cfg.serverUrl.replace(/\/$/, "")}/api/v0/workspace/files`, {
    method: "POST",
    headers: { Authorization: `Bearer ${cfg.apiKey}` },
    body: form,
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json() as Promise<PlacedWorkspaceFile>;
}
