import type { SkillResponse, WsScreenRef } from "@myguyze/ze-client";
import { useState } from "react";
import { useSkillImportMutation, useSkillTransitionMutation } from "@/entities/skill";
import { ChatAboutChip, Module } from "@/shared/ui";

type SkillRow = SkillResponse & {
  has_scripts?: boolean;
  has_unsupported_scripts?: boolean;
  executable_approved?: boolean;
  script_filenames?: string[];
};

interface Props {
  skills: SkillResponse[];
  loading: boolean;
  error: boolean;
  onChatAbout?: (ref: WsScreenRef, element?: Element | null) => void;
}

const STATUS: Record<string, string> = { pending_review: "Needs review", active: "On", disabled: "Off", rejected: "Rejected" };

function Row({ skill, onChatAbout }: { skill: SkillResponse; onChatAbout?: Props["onChatAbout"] }) {
  const transition = useSkillTransitionMutation();
  const row = skill as SkillRow;
  const scripts = Boolean(row.has_scripts ?? row.has_unsupported_scripts);
  const approved = Boolean(row.executable_approved);
  const busy = transition.isPending;
  const act = (kind: string, label: string) => (
    <button type="button" className="ctl" disabled={busy} onClick={() => transition.mutate({ skillId: skill.id, kind } as never)}>
      {label}
    </button>
  );
  return (
    <li className="row">
      <span className="t">{skill.name}</span>
      <span className="lbl">{STATUS[skill.status] ?? skill.status.replace(/_/g, " ")}</span>
      <span className="s">{skill.description}</span>
      {scripts && (
        <span className="s">
          Contains scripts{row.script_filenames?.length ? `: ${row.script_filenames.join(", ")}` : ""}.
          {approved ? " Executables approved." : " Approving the instructions does not let them run."}
        </span>
      )}
      <span className="acts">
        {skill.status === "pending_review" && (
          <>
            {act("approve", "Approve")}
            {act("reject", "Reject")}
          </>
        )}
        {skill.status === "active" && (
          <>
            {scripts && !approved && act("approve-executables", "Approve executables")}
            {act("disable", "Turn off")}
          </>
        )}
        {skill.status === "disabled" && act("enable", "Turn on")}
        {skill.source === "imported" && act("remove", "Remove")}
      </span>
      {transition.isError && (
        <span className="hot" role="alert">
          That didn't go through.
        </span>
      )}
      {onChatAbout && <ChatAboutChip label={skill.name} onClick={(chip) => onChatAbout({ kind: "skill", id: skill.id, label: skill.name } as WsScreenRef, chip.closest(".row"))} />}
    </li>
  );
}

function ImportForm() {
  const [url, setUrl] = useState("");
  const imp = useSkillImportMutation();
  const submit = () => {
    const value = url.trim();
    if (value) imp.mutate({ url: value }, { onSuccess: () => setUrl("") });
  };
  return (
    <form
      className="doing-import"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <label className="lbl" htmlFor="skill-url">
        Add a skill from a link
      </label>
      <input id="skill-url" className="doing-in" placeholder="https://example.com/SKILL.md" value={url} onChange={(e) => setUrl(e.target.value)} />
      <button type="submit" className="ctl" disabled={imp.isPending || !url.trim()}>
        Import
      </button>
      {imp.isError && (
        <p className="hot" role="alert">
          Couldn't import that skill. Check the link and try again.
        </p>
      )}
    </form>
  );
}

/** Review queue first, then what is installed. */
export function SkillsQueue({ skills, loading, error, onChatAbout }: Props) {
  const pending = skills.filter((s) => s.status === "pending_review");
  const rest = skills.filter((s) => s.status !== "pending_review");
  return (
    <Module label="Skills" tone={pending.length ? "cream" : "default"} className="doing-skills">
      <ImportForm />
      {error ? (
        <p className="hot" role="alert">
          Couldn't read your skills.
        </p>
      ) : loading ? (
        <p className="muted" role="status">
          Reading…
        </p>
      ) : skills.length === 0 ? (
        <p className="muted">No skills installed yet.</p>
      ) : (
        <>
          {pending.length > 0 && (
            <ul className="doing-list" aria-label="Waiting for your review">
              {pending.map((s) => (
                <Row key={s.id} skill={s} onChatAbout={onChatAbout} />
              ))}
            </ul>
          )}
          {rest.length > 0 && (
            <ul className="doing-list" aria-label="Installed">
              {rest.map((s) => (
                <Row key={s.id} skill={s} onChatAbout={onChatAbout} />
              ))}
            </ul>
          )}
        </>
      )}
    </Module>
  );
}
