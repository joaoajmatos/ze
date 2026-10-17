import { concernChip, concernGlyph, concernPosture, concernStateWords, pct, useReducedMotion, type Concern } from "@/shared/lib";
import { Glyph } from "@/shared/ui";
import { BANDS, bandOfConcern, shortTitle } from "../lib/placement";

interface Props {
  concerns: Concern[];
  now: Date;
  selected: string | null;
  onSelect: (key: string | null) => void;
}

/** The phone's field: the same concerns, ranked, grouped by band, with the same posture vocabulary. */
export function FieldList({ concerns, now, selected, onSelect }: Props) {
  const reduced = useReducedMotion();
  const groups = BANDS.map((b) => ({
    band: b,
    items: concerns
      .filter((c) => bandOfConcern(c, now) === b.id)
      .sort((x, y) => (x.rank ?? Infinity) - (y.rank ?? Infinity)),
  })).filter((g) => g.items.length > 0);

  return (
    <div className="field-list">
      {groups.map(({ band, items }) => (
        <section key={band.id} className={`field-band ${band.hot ? "hot" : ""}`} aria-label={band.label}>
          <h3 className={`lbl ${band.hot ? "hot" : ""}`}>
            {band.label} · {items.length}
          </h3>
          <ol className="field-key">
            {items.map((c) => {
              const posture = concernPosture(c);
              const glyph = concernGlyph(posture);
              return (
                <li key={c.key} className={`${c.slipped ? "hot" : ""} ${c.slipped && !reduced ? "slip-pulse" : ""}`}>
                  <button type="button" onClick={() => onSelect(selected === c.key ? null : c.key)} aria-pressed={selected === c.key}>
                    {glyph ? <Glyph kind={glyph} hot={c.slipped} /> : <i className="glyph plain" aria-hidden="true" />}
                    <span className="field-title">
                      {shortTitle(c.title)}
                      <span className="s"> · {concernStateWords(c)}{concernChip(posture) ? ` · ${concernChip(posture)}` : ""}</span>
                    </span>
                    <span className="ro">{c.confidence == null ? "—" : pct(c.confidence)}</span>
                  </button>
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}
