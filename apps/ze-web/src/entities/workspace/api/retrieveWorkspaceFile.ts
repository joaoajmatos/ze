import { getWorkspaceFile } from "@myguyze/ze-client";

export async function retrieveWorkspaceFile(path: string): Promise<Blob> {
  const { data, error } = await getWorkspaceFile({
    path: { file_path: path },
    parseAs: "blob",
  });
  if (error) throw error;
  return data as unknown as Blob;
}
