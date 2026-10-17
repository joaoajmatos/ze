import { useEffect, useState } from "react";
import { dayMonth, hhmm, longDate, weekday } from "@/shared/lib";
import { DotMatrix, Glyph } from "@/shared/ui";

function useClock(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 15_000);
    return () => window.clearInterval(id);
  }, []);
  return now;
}

/** One line under the top bar: the claim legend, today's date and the dot-matrix clock. */
export function Strip() {
  const now = useClock();
  return (
    <div className="strip">
      <div className="coords" title="Filled marks are told by you, half-filled are inferred, dashed are suspected. Coral means something is slipping." role="note" aria-label="Legend: filled means told, half-filled means inferred, dashed means suspected, coral means slipping">
        <span className="lbl legend-item">
          <Glyph kind="told" /> told
        </span>
        <span className="lbl legend-item">
          <Glyph kind="inferred" /> inferred
        </span>
        <span className="lbl legend-item">
          <Glyph kind="suspected" /> suspected
        </span>
        <span className="lbl legend-item">
          <Glyph kind="told" hot /> slipping
        </span>
      </div>
      <div className="clock" role="group" aria-label={`${longDate(now)}, ${hhmm(now)}`}>
        <span className="lbl only-wide">{longDate(now)}</span>
        <span className="lbl only-narrow">
          {weekday(now)} {dayMonth(now)}
        </span>
        <DotMatrix text={hhmm(now)} size={3} title={hhmm(now)} />
      </div>
    </div>
  );
}
