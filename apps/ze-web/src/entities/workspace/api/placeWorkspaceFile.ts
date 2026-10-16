import { uploadWorkspaceFile } from "@myguyze/ze-client";
import type { WorkspaceUploadResponse } from "@myguyze/ze-client";

export type PlacedWorkspaceFile = WorkspaceUploadResponse;

export async function placeWorkspaceFile(file: File, dest?: string): Promise<PlacedWorkspaceFile> {
  const { data, error } = await uploadWorkspaceFile({ body: { file, path: dest } });
  if (error) throw error;
  return data!;
}
