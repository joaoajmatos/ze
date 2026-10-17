import { useLocation } from "react-router-dom";
import { Control } from "./Control";

export interface SectionTab {
  id: string;
  label: string;
  path: string;
}

/** A row of tabs inside a place. `current` is matched on the URL, so each section stays linkable. */
export function SectionTabs({ label, sections, currentId }: { label: string; sections: readonly SectionTab[]; currentId: string }) {
  useLocation();
  return (
    <nav className="tabs section-tabs" aria-label={label}>
      {sections.map((s) => (
        <Control key={s.id} as="link" to={s.path} current={s.id === currentId}>
          {s.label}
        </Control>
      ))}
    </nav>
  );
}
