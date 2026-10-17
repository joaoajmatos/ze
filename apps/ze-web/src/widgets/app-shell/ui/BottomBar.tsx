import { useLocation } from "react-router-dom";
import { placeOf, places } from "@/shared/config";
import { Control } from "@/shared/ui";

/** The five places as icon and label, at phone width. */
export function BottomBar() {
  const current = placeOf(useLocation().pathname);
  return (
    <nav className="bottombar" aria-label="Places">
      {places.map(({ id, path, label, icon: Icon }) => (
        <Control key={id} as="link" to={path} current={current?.id === id} aria-label={label}>
          <Icon size={18} strokeWidth={1.25} aria-hidden="true" />
          <span>{label}</span>
        </Control>
      ))}
    </nav>
  );
}
