import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { TraceRow } from "./TraceRow";

interface SkillsRowProps {
  skillsUsed: WsTraceUpdateFrame["skills_used"];
  live?: boolean;
}

export function SkillsRow({ skillsUsed, live }: SkillsRowProps) {
  const skills = skillsUsed ?? [];
  return (
    <TraceRow title="Skills" count={skills.length} loading={live && skills.length === 0}>
      {skills.length === 0 ? (
        <p className="muted">No skills used</p>
      ) : (
        <ul className="tr-list">
          {skills.map((s) => (
            <li key={s.skill_id}>
              <span className="key">{s.name}</span>
              <span className="chip">{s.source}</span>
              <span className={`chip${s.trigger === "explicit" ? " solid" : ""}`}>{s.trigger}</span>
              {s.similarity != null && <span className="ro muted">{Math.round(s.similarity * 100)}%</span>}
              {s.below_floor && <span className="chip dotted">below floor</span>}
              {(s as { script_ran?: boolean }).script_ran && <span className="chip solid">script ran</span>}
            </li>
          ))}
        </ul>
      )}
    </TraceRow>
  );
}
