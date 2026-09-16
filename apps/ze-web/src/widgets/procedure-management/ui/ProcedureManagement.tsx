import { ListPage } from "@/shared/ui";
import { BookOpen } from "lucide-react";
import { useProcedureDetailQuery, useProcedureLibraryQuery } from "@/entities/procedure";
import { ProcedureControls } from "@/features/procedure-review";
import { useState } from "react";

const STATUS_LABEL: Record<string, string> = {
  active: "Active",
  retired: "Disabled",
};

function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "active"
      ? "bg-emerald-500/15 text-emerald-500"
      : "bg-foreground/10 text-smoke";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${tone}`}>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

export function ProcedureManagement() {
  const library = useProcedureLibraryQuery();
  const rows = library.data ?? [];
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined);
  const detail = useProcedureDetailQuery(selectedId);
  const selected = detail.data;

  return (
    <ListPage
      isLoading={library.isLoading}
      isError={library.isError}
      isEmpty={!library.isLoading && rows.length === 0}
      emptyIcon={BookOpen}
      emptyMessage="No procedures yet"
      emptyDetail="Admitted playbooks will appear here for inspection, revision, and disablement."
      errorMessage="Could not load procedures"
      onRetry={() => void library.refetch()}
    >
      <ul className="space-y-3">
        {rows.map((row) => (
          <li key={row.id}>
            <button
              type="button"
              className="w-full rounded-lg border border-foreground/10 px-4 py-3 text-left"
              onClick={() => setSelectedId(row.id)}
            >
              <div className="flex items-center gap-2">
                <StatusBadge status={row.identity_status} />
                <span className="truncate text-sm font-medium">{row.name}</span>
                <span className="text-xs text-smoke">v{row.version_number}</span>
              </div>
              <p className="mt-1 truncate text-xs text-smoke">{row.trigger}</p>
            </button>
          </li>
        ))}
      </ul>
      {selected ? (
        <div className="space-y-4 rounded-lg border border-foreground/10 p-4">
          <h2 className="text-sm font-medium">{selected.name}</h2>
          <p className="text-xs text-smoke">
            {STATUS_LABEL[selected.identity_status] ?? selected.identity_status}
          </p>
          <ProcedureControls detail={selected} />
          <div>
            <h3 className="mb-2 text-xs font-medium text-smoke">Evidence</h3>
            <ul className="space-y-1 text-xs text-smoke">
              {selected.versions.flatMap((version) =>
                version.evidence_refs.map((ref) => (
                  <li key={`${version.id}-${ref.id}`}>
                    {ref.kind} · {ref.id} · version {version.version_number}
                  </li>
                )),
              )}
            </ul>
          </div>
          <div>
            <h3 className="mb-2 text-xs font-medium text-smoke">Outcomes</h3>
            <ul className="space-y-1 text-xs text-smoke">
              {selected.outcomes.map((outcome) => (
                <li key={`${outcome.procedure_version_id}-${outcome.summary}`}>
                  {outcome.outcome}: {outcome.summary}
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </ListPage>
  );
}
