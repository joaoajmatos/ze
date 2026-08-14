export type WorkspaceMode = "off" | "plan" | "ask" | "auto_edit" | "auto";

export interface WorkspaceStatus {
  available: boolean;
  mode: WorkspaceMode;
  bytes_used: number;
  bytes_ceiling: number;
  busy: boolean;
  last_reset_at: string | null;
  last_used_at: string | null;
}

export interface WorkspaceFileItem {
  path: string;
  size: number;
  modified_at: string;
  is_dir: boolean;
}

export interface WorkspaceRunItem {
  id: string | null;
  started_at: string | null;
  ended_at: string | null;
  command: string;
  origin: "conversation" | "user" | "unattended";
  thread_id: string | null;
  message_id: string | null;
  skill_id: string | null;
  skill_script_path: string | null;
  status: string;
  exit_code: number | null;
  output_preview: string;
  output_file_path: string | null;
  files_touched: { path: string; op: string }[];
  error_summary: string | null;
}
