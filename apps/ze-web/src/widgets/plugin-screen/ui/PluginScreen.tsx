import { PrimitiveTreeRenderer } from "@myguyze/ze-ui/react";
import { parseTree, TreeNote, usePrimitiveActions } from "@/features/primitive-tree";
import type { UiContribution } from "@/entities/ui-manifest";
import { usePluginPageQuery } from "@/entities/ui-manifest";
import { useSetPageHeader } from "@/shared/lib";
import { EmptyState, ErrorState, ListSkeleton } from "@/shared/ui";
import { resolveNavIcon } from "@/shared/ui/icons";

export function PluginScreen({ entry }: { entry: UiContribution }) {
  const { data, isLoading, isError, refetch } = usePluginPageQuery(entry);
  const actions = usePrimitiveActions();

  const Icon = resolveNavIcon(entry.icon);

  useSetPageHeader({ title: data?.title ?? entry.label, icon: Icon });

  const parsed = data?.tree ? parseTree(data.tree, data.ui_version) : null;
  const nodes = parsed?.status === "ok" ? parsed.nodes : null;

  return (
    <div className="px-4 py-6 max-w-2xl mx-auto">
      {isLoading && <ListSkeleton count={6} />}

      {isError && (
        <ErrorState
          message={`Could not load ${entry.label.toLowerCase()}.`}
          onRetry={() => void refetch()}
        />
      )}

      {!isLoading && !isError && nodes && nodes.length === 0 && (
        <EmptyState icon={Icon} message="Nothing to show yet." />
      )}

      {!isLoading && !isError && nodes && nodes.length > 0 && (
        <PrimitiveTreeRenderer nodes={nodes} actions={actions} />
      )}

      {!isLoading && !isError && parsed?.status === "legacy-failed" && <TreeNote status="legacy-failed" />}

      {!isLoading && !isError && data && parsed?.status !== "ok" && parsed?.status !== "legacy-failed" && (
        <ErrorState message="This page returned an invalid UI tree." onRetry={() => void refetch()} />
      )}
    </div>
  );
}
