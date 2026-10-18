import { parsePrimitiveTree, type PrimitiveTree } from "@myguyze/ze-ui";
import { PrimitiveTreeRenderer } from "@myguyze/ze-ui/react";
import { ChevronDown } from "lucide-react";
import { createElement, useState } from "react";
import { usePrimitiveActions } from "@/features/primitive-tree";
import type { UiContribution } from "@/entities/ui-manifest";
import { usePluginSettingsQuery } from "@/entities/ui-manifest";
import { cn } from "@/shared/lib/cn";
import { ErrorState, ListSkeleton } from "@/shared/ui";
import { resolveNavIcon } from "@/shared/ui/icons";

export function PluginSettingsSection({ entry }: { entry: UiContribution }) {
  const [open, setOpen] = useState(true);
  const { data, isLoading, isError, refetch } = usePluginSettingsQuery(entry, open);
  const actions = usePrimitiveActions();

  let nodes: PrimitiveTree | null = null;
  if (data?.tree) {
    try {
      nodes = parsePrimitiveTree(data.tree);
    } catch {
      nodes = null;
    }
  }

  return (
    <div className="gov-stack" style={{ borderTop: "1px solid var(--hair)", paddingTop: 12 }}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="ctl-text lbl"
        style={{ display: "flex", width: "100%", alignItems: "center", justifyContent: "space-between", minHeight: 44 }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {createElement(resolveNavIcon(entry.icon), { className: "w-3.5 h-3.5", "aria-hidden": true })}
          {entry.label}
        </span>
        <ChevronDown className={cn("w-4 h-4 text-smoke transition-transform", open && "rotate-180")} />
      </button>

      {open && isLoading && <ListSkeleton count={3} />}

      {open && isError && (
        <ErrorState
          message={`Could not load ${entry.label.toLowerCase()} settings.`}
          onRetry={() => void refetch()}
        />
      )}

      {open && !isLoading && !isError && nodes && nodes.length > 0 && (
        <PrimitiveTreeRenderer nodes={nodes} actions={actions} />
      )}

      {open && !isLoading && !isError && data && !nodes && (
        <ErrorState message="Invalid settings UI tree." onRetry={() => void refetch()} />
      )}
    </div>
  );
}
