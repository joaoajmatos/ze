import { forwardRef } from "react";
import { Link, useLocation } from "react-router-dom";
import { placeOf, places } from "@/shared/config";
import { Control, DotMatrix } from "@/shared/ui";
import { ConnectionDot } from "./ConnectionDot";
import { NotificationBell } from "./NotificationBell";

/** Brand, the five places (desktop), the bell and the connection dot. `ref` is the bell's wrapper. */
export const TopBar = forwardRef<HTMLDivElement, { showTabs: boolean }>(function TopBar({ showTabs }, bellRef) {
  const current = placeOf(useLocation().pathname);
  return (
    <header className="top">
      <Link to="/" className="brand ctl-text" aria-label="Ze, home">
        <DotMatrix text="ZE" size={3} color="var(--main)" title="Ze" />
      </Link>
      {showTabs && (
        <nav className="tabs" aria-label="Places">
          {places.map(({ id, path, label }) => (
            <Control key={id} as="link" to={path} current={current?.id === id}>
              {label}
            </Control>
          ))}
        </nav>
      )}
      <div className="top-end">
        <div ref={bellRef} className="top-bell">
          <NotificationBell />
        </div>
        <ConnectionDot />
      </div>
    </header>
  );
});
