import { ApiError } from "@myguyze/ze-client";
import { getConfig } from "@/shared/config";

export async function workspaceFetch(path: string, init?: RequestInit): Promise<Response> {
  const cfg = getConfig();
  if (!cfg) throw new ApiError(401, "Not configured");
  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${cfg.apiKey}`);
  const res = await fetch(`${cfg.serverUrl.replace(/\/$/, "")}/api/v0${path}`, {
    ...init,
    headers,
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res;
}
