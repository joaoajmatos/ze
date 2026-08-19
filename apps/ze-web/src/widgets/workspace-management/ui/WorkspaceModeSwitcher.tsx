import type { WorkspaceMode } from "@/entities/workspace";

const MODES: { value: WorkspaceMode; label: string }[] = [
  { value: "off", label: "Off" },
  { value: "plan", label: "Plan" },
  { value: "ask", label: "Ask" },
  { value: "auto_edit", label: "Auto-edit" },
  { value: "auto", label: "Auto" },
];

interface WorkspaceModeSwitcherProps {
  mode: WorkspaceMode;
  onChange: (mode: WorkspaceMode) => void;
  disabled?: boolean;
  compact?: boolean;
}

export function WorkspaceModeSwitcher({
  mode,
  onChange,
  disabled,
  compact,
}: WorkspaceModeSwitcherProps) {
  return (
    <label className={`flex items-center gap-2 ${compact ? "text-xs" : "text-sm"}`}>
      <span className="text-smoke">Mode</span>
      <select
        aria-label="Workspace mode"
        value={mode}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value as WorkspaceMode)}
        className="rounded-pill border border-foreground/20 bg-background/40 px-3 py-1 text-xs text-foreground focus:outline-none focus:border-plum-voltage/50"
      >
        {MODES.map((m) => (
          <option key={m.value} value={m.value}>
            {m.label}
          </option>
        ))}
      </select>
    </label>
  );
}
