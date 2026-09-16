import { Button } from "@/shared/ui";
import { useDisableProcedureMutation, useEditProcedureMutation } from "@/entities/procedure";
import type { ProcedureDetail } from "@/entities/procedure";
import { useState } from "react";

interface ProcedureControlsProps {
  detail: ProcedureDetail;
}

export function ProcedureControls({ detail }: ProcedureControlsProps) {
  const disable = useDisableProcedureMutation();
  const edit = useEditProcedureMutation();
  const current = detail.versions.at(-1);
  const [trigger, setTrigger] = useState(current?.trigger ?? "");

  const canDisable = detail.identity_status === "active";

  return (
    <div className="flex flex-wrap items-end gap-2">
      <label className="flex min-w-48 flex-col gap-1 text-xs text-smoke">
        Trigger
        <input
          className="rounded-md border border-foreground/10 bg-transparent px-2 py-1 text-sm text-foreground"
          value={trigger}
          onChange={(event) => setTrigger(event.target.value)}
        />
      </label>
      <Button
        size="sm"
        variant="outline"
        disabled={edit.isPending || current == null}
        onClick={() => {
          if (current == null) {
            return;
          }
          edit.mutate({
            procedureId: detail.id,
            name: current.name,
            trigger,
            preconditions: current.preconditions,
            steps: current.steps,
            success_criteria: current.success_criteria,
            limits: current.limits,
            reason: "edited from procedure management",
          });
        }}
      >
        Save revision
      </Button>
      {canDisable ? (
        <Button
          size="sm"
          variant="outline"
          disabled={disable.isPending}
          onClick={() =>
            disable.mutate({
              procedureId: detail.id,
              reason: "disabled from procedure management",
            })
          }
        >
          Disable
        </Button>
      ) : null}
    </div>
  );
}
