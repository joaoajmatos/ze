import type { WsTraceUpdateFrame } from "@myguyze/ze-client";
import { TraceSection } from "@/widgets/message-trace/ui/TraceSection";

interface SkillsSectionProps {
  skillsUsed: WsTraceUpdateFrame["skills_used"];
  live?: boolean;
}

export function SkillsSection({ skillsUsed, live }: SkillsSectionProps) {
  const skills = skillsUsed ?? [];
  return (
    <TraceSection title="Skills" count={skills.length} loading={live && skills.length === 0}>
      {skills.length === 0 ? (
        <p className="text-xs text-smoke/80 italic">No skills used</p>
      ) : (
        <ul className="space-y-1.5">
          {skills.map((s) => (
            <li key={s.skill_id} className="flex items-center gap-2 text-xs">
              <span className="font-mono text-white/90">{s.name}</span>
              <span className="px-1.5 py-0.5 rounded bg-white/[0.06] text-smoke text-[10px]">
                {s.source}
              </span>
              <span
                className={`px-1.5 py-0.5 rounded text-[10px] ${
                  s.trigger === "explicit"
                    ? "bg-plum-voltage/20 text-plum-voltage"
                    : "bg-white/[0.06] text-smoke"
                }`}
              >
                {s.trigger}
              </span>
              {s.similarity != null && (
                <span className="text-smoke/80">{Math.round(s.similarity * 100)}%</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </TraceSection>
  );
}
