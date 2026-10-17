---
version: 1
slug: "apps-ze-web-src-pages-home"
primary_target: "apps/ze-web/src/pages/home"
related_targets: []
---

# Home dashboard (world-state) — surface brief

Scope: the ze-web home route and the shell every other screen inherits. Mode: Operate.
Audience: one user, desktop mornings and phone through the day. Job: see what is open,
drifting and promised; answer what Ze needs; check what Ze did unattended; trust it via
kind, source and confidence. Build path: code-led (Operate).

Status: prototype round. Three directions are built on the throwaway branch
`web-reimagine-protos` under `/proto/*`. The user picks one (or a mix); the pick becomes the
single direction contract below and DESIGN.md is written at finish.

## Direction contract — A. Almanac (assigned)

THESIS: Attention is a tide you can read ahead of time. The home is the day's almanac of
concerns, not a grid of equal tiles.
OWN-WORLD: Printed tide-table discipline. Cool chart-white ground, harbour-navy ink and
shell, one signal red for high water (due, drifting), sea green for closed, sand for
suspected. Archivo in one text size; rank by weight, case, rule and reversal. Hairline rules,
tabular figures, no cards.
STORY: The user reads today's high water, clears what needs their OK, and sees each claim's
kind and confidence without opening anything.
FIRST VIEWPORT: Navy top bar with tabs and an Ask Ze field. Full-width attention tide for the
next 7 days with high/low water labels. Below, four ruled columns: Needs you, Ranked,
Coming due, While you were away.
FORM: Tide table / nautical almanac, position 6 of 7. seed:0c45ef5e65c8794a
Raise (from rw-timetable-slide-rack, declined): one type size; rank by weight and case only.
Raise (from vernacular-ephemera-jet-age-ticket-wallet, declined): nothing disappears; closed
and dropped items stamp, they do not vanish.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Direction contract — B. Outlook (Impeccable's pick)

THESIS: Every claim is a forecast. Confidence reads like a probability of rain, with a band
that widens as evidence ages.
OWN-WORLD: National weather service outlook. Deep teal shell rail, light green-grey ground,
front colors for state (cold-front blue = active, warm-front red = drifting, occluded plum =
Ze's own inference). Barlow and Barlow Semi Condensed. Probability bands are the only chart
ornament.
STORY: The user reads a plain-language outlook, the week ahead, and how sure Ze is about
each concern and belief.
FIRST VIEWPORT: Left rail nav. A 7-day outlook strip leads; under it the forecast
discussion (generated from data, not an LLM) beside the ranked concerns with probability
bands; needs-you queue on the right.
FORM: Weather forecast outlook, position 1 of 7. seed:0c45ef5e65c8794a
Risk: the most familiar of the three; a weather metaphor can turn twee if it names things
"sunny".
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Direction contract — C. Exposure (challenger, competitive)

THESIS: Observation and interpretation look different. Plain tones are what Ze saw; magenta
is what Ze concluded; hatch density is how sure it is; crossed hatches are a conflict.
OWN-WORLD: Darkroom exposure record. Eleven-step zone ramp as the only neutrals on a dark
ground, one dichroic magenta for Ze's inferences and suspicions. Sofia Sans, Sofia Sans
Extra Condensed caps for legends, Martian Mono for quantities.
STORY: The user sees the four faces of the world-state as stacked sheets, one decision at a
time on the left, and an exposure log of what Ze did on the right.
FIRST VIEWPORT: Command-first: a wide Ask Ze bar on top. Three work areas: Needs you (one
item expanded), the world-state sheets (active concerns, people and projects, you, Ze), the
activity log with the interruption budget.
FORM: operate-b-exposure-record-zone-sheets (catalog challenger, fused). seed:0c45ef5e65c8794a
Kept from declined digital-design-canon-warm-consumer-app-surface: the one bright color is
always something you can press, except magenta, which only marks Ze's own conclusions.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Direction contract — D. Keil tiles (replacement world, 2026-10-17)

THESIS: Priority is a position, not a list. Every claim has a place on one glazed tile field,
by time left and by how sure Ze is, and the page refuses the equal-card grid and the stat tile.
OWN-WORLD: Maria Keil's Lisbon Metro station panels. Warm glaze-white ground, grout hairlines at
one device pixel, cobalt for what Ze saw or was told, ochre for what Ze concluded, oxide red for
what slipped, graphite for closed. Color commits at region scale: a cobalt rail, ochre and red
fields where state lives. One family, Hanken Grotesk, weight and size for rank; tabular figures.
Confidence is glaze: a sure claim is a full glazed tile, a decayed one goes matte toward bisque.
STORY: The user reads where everything stands in one look, clears what needs their OK, sees who
and what is in play, and trusts each claim because its kind, source and age show on the tile.
FIRST VIEWPORT: Cobalt left rail (Today, Talk, Concerns, People, Beliefs, Goals, Workflows,
Settings). Top: date, Ask Ze, interruption tiles. Left third: Needs you, one decision open, the
queue below. Right two thirds: the tile field "Where everything stands" (x time left, y sureness,
gutter no deadline). Below: ranked concerns with runway, then Ze on its own.
Cross-surface: Concerns (field + filters + stamped), People and projects (who is in play, by
project tile band, matched to concerns), Beliefs (the user-model: facts as glaze tiles by
confidence and age, unreviewed in ochre).
Signature interaction: hovering or focusing any tile lifts it and shows kind, source, age; its
row lights; decayed tiles read matte before any number is read.
Honest risk: azulejo can turn souvenir; keep the grid strict and the palette to five inks.
Raise (from digital-design-canon-metro-typographic-tiles, competitive): no chrome, color fields
as content, one accent owns every live state. Raise (from ikeda-datamatics, declined): data
density in the margins, tabular numerals. Raise (from rw-centre-rail, declined): every rule at
one device pixel. Kept (jet-age ticket wallet, declined): nothing disappears, it stamps. Kept
(vertical feed, declined): one decision at a time with the next waiting.
FORM: Maria Keil Metro tile panel, position 4 of 7. seed:44c0f30b032d4a0e
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Declined challengers

- pop-culture-shelf-vertical-video-feed-surface: declined. Kept: one decision at a time with
  the next already waiting (used in C's Needs you queue and every phone layout).
- brand-identity-canon-saville-catalog-sleeve: declined. Kept: only the active item decodes
  to full color.

## Unresolved

- Which direction (or mix). Light-only, dark-only, or both themes.
- Backend gaps the prototypes mark as synthetic (see the floor handoff note).
