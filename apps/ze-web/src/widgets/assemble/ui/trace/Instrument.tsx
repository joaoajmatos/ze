import { useId, useState, type ReactNode } from "react";

/** One collapsed line of the rail: the name and its main readout; opens on click, Enter, hover or focus. */
export function Instrument({ name, readout, open: openProp, children, id }: { name: string; readout: string; open?: boolean; children: ReactNode; id?: string }) {
  const [openState, setOpen] = useState(false);
  const panel = useId();
  const open = openProp ?? openState;
  return (
    <section className="tr-instrument" data-instrument={id ?? name.toLowerCase()} data-open={open ? "" : undefined}>
      <button type="button" className="tr-instrument-head" aria-expanded={open} aria-controls={panel} onClick={() => setOpen(!open)}>
        <span className="lbl">{name}</span>
        <span className="ro" title={readout}>{readout}</span>
      </button>
      {open && (
        <div id={panel} className="tr-instrument-body">
          {children}
        </div>
      )}
    </section>
  );
}
