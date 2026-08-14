import { workspaceFetch } from "./workspaceFetch";

export async function retrieveWorkspaceFile(path: string): Promise<Blob> {
  const res = await workspaceFetch(`/workspace/files/${encodeURIComponent(path)}`);
  return res.blob();
}
