import type { SkillResponse } from "@myguyze/ze-client";
import { PenTool } from "lucide-react";
import { useState } from "react";
import {
  useSkillImportMutation,
  useSkillsQuery,
  useSkillTransitionMutation,
} from "@/entities/skill";
import { Button, Input, ListPage } from "@/shared/ui";

type SkillRow = SkillResponse & {
  has_scripts?: boolean;
  has_unsupported_scripts?: boolean;
  executable_approved?: boolean;
  script_filenames?: string[];
};

const STATUS_LABEL: Record<string, string> = {
  pending_review: "Pending review",
  active: "Active",
  disabled: "Disabled",
  rejected: "Rejected",
};

function skillHasScripts(skill: SkillRow): boolean {
  return Boolean(skill.has_scripts ?? skill.has_unsupported_scripts);
}

function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "active"
      ? "bg-emerald-500/15 text-emerald-500"
      : status === "pending_review"
        ? "bg-amber-500/15 text-amber-500"
        : status === "disabled"
          ? "bg-foreground/10 text-smoke"
          : "bg-destructive/15 text-destructive";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${tone}`}
    >
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

function SourceBadge({ source }: { source: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-foreground/5 px-2 py-0.5 text-xs text-smoke">
      {source}
    </span>
  );
}

function SkillRow({ skill }: { skill: SkillResponse }) {
  const transition = useSkillTransitionMutation();
  const row = skill as SkillRow;
  const hasScripts = skillHasScripts(row);
  const executablesApproved = Boolean(row.executable_approved);

  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-foreground/10 px-4 py-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <StatusBadge status={skill.status} />
          <SourceBadge source={skill.source} />
          <span className="truncate text-sm font-medium">{skill.name}</span>
        </div>
        <p className="mt-1 truncate text-xs text-smoke">{skill.description}</p>
        {hasScripts && (
          <p className="mt-1 text-xs text-amber-spark">
            Contains scripts
            {row.script_filenames?.length ? `: ${row.script_filenames.join(", ")}` : ""}.
            {executablesApproved
              ? " Executables approved."
              : " Instructions approval does not run them."}
          </p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {skill.status === "pending_review" && (
          <>
            <Button
              size="sm"
              variant="outline"
              disabled={transition.isPending}
              onClick={() => transition.mutate({ skillId: skill.id, kind: "approve" })}
            >
              Approve
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={transition.isPending}
              onClick={() => transition.mutate({ skillId: skill.id, kind: "reject" })}
            >
              Reject
            </Button>
          </>
        )}
        {skill.status === "active" && (
          <>
            {hasScripts && !executablesApproved && (
              <Button
                size="sm"
                variant="outline"
                disabled={transition.isPending}
                onClick={() =>
                  transition.mutate({ skillId: skill.id, kind: "approve-executables" })
                }
              >
                Approve executables
              </Button>
            )}
            <Button
              size="sm"
              variant="outline"
              disabled={transition.isPending}
              onClick={() => transition.mutate({ skillId: skill.id, kind: "disable" })}
            >
              Disable
            </Button>
          </>
        )}
        {skill.status === "disabled" && (
          <Button
            size="sm"
            variant="outline"
            disabled={transition.isPending}
            onClick={() => transition.mutate({ skillId: skill.id, kind: "enable" })}
          >
            Enable
          </Button>
        )}
        {skill.source === "imported" && (
          <Button
            size="sm"
            variant="ghost"
            disabled={transition.isPending}
            onClick={() => transition.mutate({ skillId: skill.id, kind: "remove" })}
          >
            Remove
          </Button>
        )}
      </div>
    </div>
  );
}

function ImportSkillForm() {
  const [url, setUrl] = useState("");
  const importSkill = useSkillImportMutation();

  function submit() {
    if (!url.trim()) return;
    importSkill.mutate(
      { url: url.trim() },
      { onSuccess: () => setUrl("") },
    );
  }

  return (
    <div className="flex items-center gap-2">
      <Input
        className="h-8"
        placeholder="https://example.com/SKILL.md"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") submit();
        }}
      />
      <Button size="sm" disabled={importSkill.isPending || !url.trim()} onClick={submit}>
        Import
      </Button>
    </div>
  );
}

export function SkillManagementList() {
  const { data: skills, isLoading, isError, refetch } = useSkillsQuery();

  return (
    <div className="space-y-4">
      <ImportSkillForm />
      <ListPage
        isLoading={isLoading}
        isError={isError}
        isEmpty={!skills?.length}
        emptyIcon={PenTool}
        emptyMessage="No skills installed yet."
        errorMessage="Could not load skills."
        onRetry={() => void refetch()}
      >
        <div className="space-y-2">
          {skills?.map((skill) => <SkillRow key={skill.id} skill={skill} />)}
        </div>
      </ListPage>
    </div>
  );
}
