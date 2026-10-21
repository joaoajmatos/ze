---
name: Ze
description: One mind writing to one world-state, shown as a quiet HUD in purple light
colors:
  field: "#120d14"
  orchid: "#b9a3ff"
  ultraviolet: "#9e82ff"
  amethyst: "#c08cff"
  coral: "#ff6f63"
  cream: "#efe5d7"
  dim: "#9a90ae"
  field-ultraviolet: "#0b0a14"
  field-amethyst: "#0e0a17"
typography:
  display:
    fontFamily: "DotMatrix (authored 5x7 dot glyphs, SVG), fallback Michroma"
    fontSize: "dot pitch 2.6 to 5 px per dot; 4 px on desktop headlines"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "one dot column"
  numeral-lg:
    fontFamily: "Saira, system-ui, sans-serif"
    fontSize: "2rem"
    fontWeight: 200
    lineHeight: 1
    letterSpacing: "-0.01em"
  numeral-md:
    fontFamily: "Saira, system-ui, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 200
    lineHeight: 1
    letterSpacing: "-0.01em"
  input:
    fontFamily: "Saira, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 300
    lineHeight: 1.4
    letterSpacing: "normal"
  sentence:
    fontFamily: "Saira, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 300
    lineHeight: 1.5
    letterSpacing: "normal"
  title:
    fontFamily: "Saira, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 300
    lineHeight: 1.4
    letterSpacing: "normal"
  body:
    fontFamily: "Saira, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 300
    lineHeight: 1.45
    letterSpacing: "normal"
  note:
    fontFamily: "Saira, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 300
    lineHeight: 1.45
    letterSpacing: "normal"
  small:
    fontFamily: "Saira, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 300
    lineHeight: 1.4
    letterSpacing: "normal"
  chip:
    fontFamily: "Michroma, Saira, system-ui, sans-serif"
    fontSize: "0.5625rem"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "0.16em"
  label:
    fontFamily: "Michroma, Saira, system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "0.22em"
  readout:
    fontFamily: "JetBrains Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "0.75rem"
    fontWeight: 300
    lineHeight: 1.2
    letterSpacing: "0.04em"
  micro:
    fontFamily: "JetBrains Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "0.6875rem"
    fontWeight: 300
    lineHeight: 1.2
    letterSpacing: "0.08em"
  tiny-label:
    fontFamily: "Michroma, Saira, system-ui, sans-serif"
    fontSize: "0.5rem"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "0.1em"
  chart-tick:
    fontFamily: "Michroma, Saira, system-ui, sans-serif"
    fontSize: "8px"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.1em"
  chart-label:
    fontFamily: "Saira, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "normal"
rounded:
  none: "0px"
spacing:
  hair: "1px"
  xs: "4px"
  sm: "8px"
  md: "14px"
  lg: "18px"
  xl: "28px"
  touch: "44px"
components:
  module:
    backgroundColor: "linear-gradient(180deg, color-mix(in oklab, {colors.orchid} 7%, transparent), transparent 34%), color-mix(in oklab, color-mix(in oklab, {colors.orchid} 7%, {colors.field}) 70%, transparent)"
    textColor: "{colors.cream}"
    rounded: "{rounded.none}"
    padding: "14px 14px 12px"
  control:
    backgroundColor: "transparent"
    textColor: "{colors.cream}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0 14px"
    height: "{spacing.touch}"
  control-active:
    backgroundColor: "transparent"
    textColor: "{colors.cream}"
    rounded: "{rounded.none}"
    padding: "0 14px"
  command-chip:
    backgroundColor: "transparent"
    textColor: "{colors.cream}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "8px 12px 8px 10px"
  chip:
    backgroundColor: "transparent"
    textColor: "{colors.dim}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "4px 7px"
  ask-input:
    backgroundColor: "transparent"
    textColor: "{colors.cream}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    height: "{spacing.touch}"
---

# Design System: Ze

Source of truth for the web app (`apps/ze-web`). Every token below is a CSS custom property on
`:root` in `apps/ze-web/src/shared/styles/ze.css`; the five places are the reference implementation. Build from this file and that CSS;
when they disagree, this file wins and the CSS gets fixed.

## Overview

**Creative North Star: "The Quiet Instrument"**

Ze is one mind writing to one world-state, and the interface is the instrument panel that shows
that state. The world is GMUNK's Oblivion and TET screens crossed with Nothing OS dot-matrix type:
hairline frames with bracketed corners on a near-black plum field, a purple key light, small
letter-spaced labels beside thin numerals, a dotted sphere that breathes while Ze listens and
flares coral when something slips. Nothing is decorated for its own sake. Every line, dot and tone
encodes a fact about what Ze knows, how sure it is, and what it is doing about it.

The register is calm. There is one state, no cinematic mode. Light carries depth (an inner
gradient, an inset top edge, brackets that brighten), never shadows. Motion is continuous: the
orb morphs with springs, answers assemble from the orb's position, text decodes in, numbers tick
up, hairlines draw on. The user is one technical person who reads confidence values and
provenance without softening, so the UI shows them plainly and makes their posture visible: a
suspicion is asked, a fact is stated, a slip is coral.

Confirmed rejections: the generic AI-dark look (purple pills on cards, Space Grotesk, Inter),
equal-weight card stacks, pie charts and decorative heatmaps, ALL-CAPS outline pill buttons two
to a row, flat lavender fills with dark text, drop shadows and backdrop blur, and a chat window as
the home screen.

**Key Characteristics:**
- Purple-led: Orchid is the default; Ultraviolet and Amethyst are alternate palettes with the same structure
- Coral is reserved for one meaning: something has slipped and needs attention
- Four brightness levels used on purpose: cream for names and key values, orchid for live values and structure, dim for secondary text, faint for scaffolding
- Hairline frames with bracketed corners; zero radius everywhere
- Dot-matrix display type for the big moments, Michroma micro-labels, Saira body, JetBrains Mono readouts
- Honesty visuals travel with every claim: filled told, half inferred, dashed suspected, hollow goal, coral slipped, dotted trail for decayed confidence
- The orb is the presence: nine states, continuous spring morphs, a heartbeat that the rest of the page can sync to. Its idle gaze is the one decoration: it never carries a fact and never overrides a state

## Colors

A near-black plum field lit by one purple, with cream for what matters and coral for what slipped.

### Primary
- **Orchid** (`#b9a3ff`): the default palette and key light (user pick, 2026-10-17); the palette switcher lives in Governance. Live values, structure (hairlines, brackets, grid), the lit sphere, active controls, told marks. Set as `--main`.
- **Ultraviolet** (`#9e82ff`) and **Amethyst** (`#c08cff`): alternate palettes selected with `data-palette` on the root. Each swaps `--main`, `--field`, `--dim`, `--coral`, `--cream` together; nothing else changes. Inside the orb, the three purples form one gradient (Ultraviolet → Amethyst → Orchid, mixed in oklab) that some states use (listening edge to core, thinking swirl, speaking ripples, one tone per acting ring).

### Secondary
- **Coral** (`#ff6f63`; `#ff6e5a` ultraviolet, `#ff7a60` amethyst): slipped concerns, the attention orb and its leader line, failed runs. It is never used for emphasis, selection or "needs you".

### Neutral
- **Field** (`#120d14`; `#0b0a14` ultraviolet, `#0e0a17` amethyst): the page and the inside of the field chart.
- **Cream** (`#efe5d7`): names, the answer sentence, key numerals, the orb core, focused frames. Level 1 brightness.
- **Ink** (`color-mix(in oklab, cream 92%, orchid)`): headline-grade text. **Ink-2** (`color-mix(in oklab, cream 74%, field)`): default body text (about 7:1 on the field).
- **Dim** (`#9a90ae`): secondary text, labels at rest, suspected marks. Level 3. **Faint** (`color-mix(in oklab, dim 55%, field)`): scaffolding only. Level 4.
- Derived structure, all mixed in oklab from `--main`: `--hair` 28% (frames), `--hair-strong` 55% (focused frames, axis ticks), `--wash` 7% and `--wash-2` 13% over the field (module backgrounds), `--glow` 45% (orb halo), `--band` 5% (chart bands), `--band-hot` coral 9% (the slipped band), `--coral-glow` coral 45%.

### Named Rules
**The One Alarm Rule.** Coral means slipped. A gate, a suspicion or a confirmation that needs the user is cream, never coral. Failed unattended runs may be coral because they are alarms.
**The Four Levels Rule.** Every text element is on one of four levels: cream (names, key values), orchid (live values, structure), dim (secondary), faint (scaffolding). Do not invent a fifth.
**The Light Rule.** Depth comes from light on a surface (top gradient, inset top edge, brackets that brighten), never from a shadow under it.

## Typography

**Display Font:** DotMatrix, an authored 5×7 dot-glyph renderer (`hud/DotMatrix.tsx`, SVG dots), with Michroma as the text fallback.
**Label Font:** Michroma (with Saira, then system-ui).
**Body Font:** Saira 200/300/400 (with system-ui).
**Readout Font:** JetBrains Mono 300/400 (with ui-monospace).

**Character:** wide, tracked, machine-set labels next to thin humanist numerals and dot-matrix headlines. The mix is what makes a panel read as an instrument rather than a page. Mono is for data only: times, ratios, ids, deltas.

### Hierarchy
- **Display** (DotMatrix, 4 px pitch on desktop, 2.6 px on phones, 5 px for the session clock at 2.4): the answer headline ("2 SLIPPING · 1 AT RISK"), the clock. Rendered as real dots so it also reads as the Nothing OS bridge to the orb.
- **Numeral** (Saira 200, 1.375rem `.num.md` / 2rem `.num.lg`, line-height 1, cream, tabular): counts and day deltas ("3 D"). Counts tick up on arrival.
- **Sentence** (Saira 300, 1.125rem, line-height 1.5, cream, max 62ch, `text-wrap: pretty`): the one plain-language sentence Ze speaks on a view, and card titles at 1.0625rem.
- **Body** (Saira 300, 0.9375rem, line-height 1.45, ink-2): descriptions and row text. Key nouns inside body get `.key` (cream). Rows' titles are cream.
- **Label** (Michroma 400, 0.6875rem, 0.22em tracking, uppercase, dim at rest, orchid when live, coral when slipped): module names (rendered as `h2`), axis and band titles, chips at 0.5625rem / 0.16em.
- **Readout** (JetBrains Mono 300, 0.75rem, 0.04em, tabular, cream; orchid `.on`, coral `.hot`): "synced 14:27", "0.74 ▾0.05", "2/4", "in 3 days 09:00", key hints. **Micro** (0.6875rem, 0.08em) for deltas, chip indices and key hints. **Input** (Saira 1rem) for the Ask bar. Inside fixed-viewBox SVG timelines, ticks are Michroma 8px and labels Saira 11px (viewBox units); the field chart uses the px-true rule instead.
- **Title** (Saira 300, 1.0625rem, line-height 1.4, cream): card titles on the Assemble canvas.
- **Note** (Saira 300, 0.875rem, ink-2 or dim): a card's supporting line, offers and held-for-OK notes.
- **Small** (`.s`, 0.8125rem, dim): the second line of a row.

### Named Rules
**The Mono-Is-Data Rule.** JetBrains Mono appears only on numbers, times, ids and deltas. A word in mono is a mistake.
**The Px-True Chart Type Rule.** SVG charts scale to their container, so chart text is sized as `calc(13px * var(--k))` where `--k` is viewBox units per CSS pixel (set by a ResizeObserver). Chart type is the same size on every screen.
**The No-Kicker Rule.** Module labels are the heading; no eyebrow above a heading, no title duplicated from the top bar.

## Layout

Desktop (≥1024px) is a three-column instrument: a 264px left rail (presence, governance, doing now, needs you), a fluid hero (the world-state field or the assembled answer), a 300px right rail (loops, inflows, while-you-were-away). Grid `264px minmax(0,1fr) 300px`, 14px gaps, 12px 16px page padding; top bar with brand, view tabs and the prototype group; a one-line strip (legend, date, dot-matrix clock); a sticky Ask bar at the bottom (44px input, mic, Ask).

The assembled answer is a 12-column canvas (`.canvas`, 14px gap, `grid-auto-flow: dense`) where each component declares a span of 4, 6, 8 or 12. Components fly in from the orb's measured position, 80ms apart.

Rhythm: 14px inside modules, 7px vertical per row, 10px between module sections (`.rule`), 18px hero padding, 28px left page gutter on desktop. Touch targets are 44px minimum, including chart marks (hit radius 26 units on desktop, 60 on phones) and tools.

Phone (≤1023px): one column with 16px gutters and no horizontal scroll (`.shell { grid-template-columns: minmax(0,1fr) }`, root `overflow-x: clip`). The rails become `display: contents` so modules reorder: presence first, then the hero with its sentence and CTA above the field, then Needs you, then the rest. The field plot is desktop-only; phones get the same concerns as a ranked list grouped by band (Slipped, This week, Later, No deadline) with glyph, title and confidence readout. Canvas spans collapse to 12. The prototype controls fold into a closed `<details>`.

## Elevation & Depth

No drop shadows and no backdrop blur. Depth is light on a surface:

- A module carries a top gradient (`linear-gradient(180deg, color-mix(in oklab, var(--main) 7%, transparent), transparent 34%)`) over a 70% wash, and an inset top edge (`box-shadow: inset 0 1px 0 color-mix(in oklab, var(--main) 22%, transparent)`). On hover or focus-within the frame goes to `--hair-strong`, the inset edge to 40%, and the 9px bracket corners grow to 12px and turn cream (220ms).
- The hero viewport sits one plane above the page: a 1px `--hair-strong` frame, a 45% wash, 18px cream-less corner brackets, and a 20px dot grid inside it only (`.hero-body::before`, radial-masked so it fades at the edges, alpha 0.035). The dot grid never appears under rails or chips.
- Active controls bloom from below (`inset 0 -16px 26px -14px color-mix(in oklab, var(--main) 55%, transparent)`); the primary control adds a 1px inner stroke. No flat fills.
- The orb has one static halo behind it (`.presence-orb::before`, radial gradient of `--glow`, opacity 0.55). Nothing else glows at rest.
- The sticky Ask bar is 97% field, no blur.

### Named Rules
**The Flat-At-Rest Rule.** Surfaces are flat at rest; light appears on hover, focus and activity.
**The No-Halo Rule.** Zero-offset glows are allowed only on the orb and the attention leader tip.

## Shapes

Zero radius everywhere: modules, controls, chips, inputs, chart marks. Frames are 1px hairlines (`--hair`) with four bracketed corners drawn as 9px `<i class="corner">` elements (18px on the hero). Controls draw their own 7px brackets with eight background-image strokes. Marks are 11-unit squares; the goal mark is the same square rotated 45°. Meters are 3px tick bars; budget dots are 7px circles. Sparklines are 46×14 polylines. The orb is the only circle, and it is made of dots.

## Components

### Buttons (`.ctl`)
- **Shape:** zero radius, 44px minimum height and width, 1px `--hair` border, 7px bracket corners in `--c` (orchid; cream when active), Michroma label 0.625rem / 0.18em uppercase, ink text.
- **Hover:** border to `--hair-strong`, text to cream, a light sweep (`::before` gradient translating -110% → 110%, 600ms, ease-out).
- **Active / pressed / current / primary:** cream brackets, orchid border, cream text, bloom from below (see Elevation). Primary adds the inner stroke and a stronger bloom on hover. Never a flat fill with dark text.
- **Disabled:** dim text, hair border, no opacity change.
- **Tabs:** the same control with a transparent border and a 1px bottom hairline; current tab has a 2px orchid bottom border and cream text.
- **Text button (`.ctl-text`):** unstyled text that keeps the cream focus ring.

### Command chips (`.ctl.cmd`)
Left-aligned command rows for questions and navigation: a mono index ("01"), the query in Saira 0.9375rem, a mono key hint in a 1px hair box ("1"). Keys 1–3 fire them. Pressed state = bloom + cream brackets + cream key hint. Used for "Try" presets and "← Back to the world".

### Chips (`.chip`)
Michroma 0.5625rem / 0.16em uppercase, dim, 1px hair border, 4px 7px padding. `.solid` for a stated source, `.dotted` (dashed border) for an inference ("asked, not stated", "risk is Ze's read"). Chips carry provenance and posture only; no decorative badges.

### Modules (`.mod`, `shared/ui/hud/Module.tsx`)
- **Head:** `h2.lbl` label (orchid; cream for `tone="cream"`, coral for `tone="hot"`), right slot with tools (pin, dismiss, 44px). Instrument ids (01, 02 …) appear only on the Assemble canvas, where the index is the component's position in the answer (user decision 2026-10-17); World, Doing, Mind and Governance modules carry no coordinate. Label never wraps (ellipsis); the right slot never shrinks.
- **Body:** rows (`.row`: 1fr auto grid, 7px padding, 14% hairline between), `.rule` dividers that draw on (scaleX, 700ms), meters, sparklines, chips, actions.
- **Tones:** default; `cream` (needs the user: gates, confirmations); `hot` (slipped, failed); `dotted` (suspected: dashed frame).
- **Hover / focus-within:** frame and brackets brighten as in Elevation.

### Chat about this (`.chat-about`, `shared/ui/hud/ChatAboutChip.tsx`)
A bracketed chip (`.ctl.cmd` family, 44px target) in a module head's right slot, labelled "Chat about this". With a hover-capable pointer it stays visually hidden (opacity and transform) but present and focusable, and shows on hover or focus-within. On touch it is always visible. `c`, with no modifiers and outside an input, triggers it while focus is inside the module. Components without a `Module` frame use the chip directly with the same rules. Pressing it opens the Ask overlay on that record, and the orb glances at the element.

### Trace instruments (`widgets/assemble/ui/trace/`)
The trace is a rail of instruments beside the answer, calm by default. The head says "trace", holds the thumbs and a coordinate line ("Asked from · Doing › Goal · Run 5k"). Under it the Signal path is a hairline from a cream origin point with one tick per stage that arrived, each with a mono "+1.2 s" readout; the newest tick is lit while the turn streams. Below it, one collapsed line per instrument shows its main readout and opens on click, Enter or focus: Routing (a confidence bar labelled by what produced it, the options as needles, the tier line), Memory (a constellation, relevance across and extraction confidence up, null confidence on a dashed floor), Tools (a lane per agent, each on its own axis, with the caption "order and duration per lane; start times not recorded"), Judgments (grouped by where the answer was used, with skip reasons in words), Reversal (last undone action first). Readouts end the rail: total in dot matrix, model, the System One line.
- **No invented data.** Every mark comes from `MessageTrace` or `trace_update`. A number carries the name of its source. No threshold lines, no cost, no context meter, no overlap between lanes, no duration from a live call.
- **No coral.** Nothing in a trace has slipped. Failure and denial read as text and a dashed mark.
- Reduced motion removes the sweep. Every value is also text or an `aria-label`. Phones get the same rail in a dialog.

### Rows (`.row`, `.row.loop`)
Title in cream with a claim glyph (`.glyph`: filled told, half inferred, dashed suspected, rotated hollow goal; coral when slipped), a 1px state tick on the left (orchid active, coral drifting, dim suspected or awaiting gate), a confidence sparkline (`Spark`: from the value when last evidenced to the decayed value now; dashed when inferred or suspected) over a mono readout "0.74 ▾0.05", and a dim second line "Drifting · chat · 3d ago". `SeriesSpark` draws a series; `Spark` draws a two-point change.

### Meters and dots
`Meter`: 12 tick bars, 3px wide, orchid lit; `.dotted` half-height for inferred; `.hot` coral. Always paired with the value as text or `aria-valuetext`. `Dots`: the push budget, N circles, lit = spent, with a mono "0/5" beside it.

### Inputs (Ask bar)
Zero radius, 1px `--hair-strong` border, transparent background, Saira body text in cream, placeholder dim, 44px height, focus ring 1px cream offset 3px (global `:focus-visible`). Caret, selection and scrollbars are themed from `--main`.

**Mic (`features/voice-input/ui/VoiceMic.tsx`).** A 44px `.ctl` beside the input, labelled "Speak to Ze (hold V)". Hold `V` outside a text field to talk; a hold under 300 ms is discarded. States: idle (mic glyph); recording (`aria-pressed`, stop square and a mono clock that becomes "Ns left" from 105 s, hard stop at 115 s); transcribing (disabled, `aria-busy`); unavailable or blocked (disabled, the reason is the label and title). A one-line status above the bar (`VoiceStatus`, `role="status"`) carries the words: "Transcribing…", "10 seconds left", "Ze heard nothing", and failures with a 44px Retry, "Try again" or "Record again", and Dismiss. Ambience goes silent while recording.

### Navigation
Top bar: dot-matrix "ZE" brand, the five places as tabs (World, Ask, Doing, Mind, Governance), the notification bell and a connection dot. No prototype controls: the palette is a Governance setting. Phone (1023px and below): the tabs leave the top bar and a fixed bottom bar shows the five places as icon and label, each a 44px target. The Ask bar sits directly above it. Inside a place, sections are a row of tabs (`SectionTabs`). Secondary lists (Needs you, Doing now, sessions) live in the shell rail under the Presence orb, through `rail-slot`, never in the place's canvas.

### Presence module (signature)
A framed module at the top of the left rail: "● Online", the dot-matrix session clock and the ambience toggle (a 44px `.ctl`, `aria-pressed`, "Ambience on" / "Ambience off") in the head, the orb (184px; 120px compact) with no waveform strip under it (speaking shows through the orb's own pulse), and a footer with a `presence` label and the state phrase ("2 promises slipping", "composing", "assembling the answer") with `aria-live` only for attention, done and error.

**Ambience (`features/ambience`).** An opt-in synthesized hum, off by default, remembered per browser (`ze.ambience`) and started only by a gesture. It ducks to silence while the mic records. Under reduced motion it reads off until the user presses the toggle.

### The orb (`shared/ui/hud/presence/Orb.tsx`, signature)
A dot-matrix sphere on a 29-dot grid drawn on canvas: denser and brighter toward a lit cream core, a drifting key light, a limb rim. Every dot keeps its grid home and springs (K=110, critically damped) toward where the current state wants it. A state change reaches the rim 320ms after the core (`stagger = (0.75·r + 0.25·seed) × 320ms`), so every transition is one continuous morph, never a cut or crossfade. Colours mix in oklab; coral drains back at a quarter of the normal rate.

**The monad (the user's direction, 2026-10-17).** The white point at the orb's core is Ze's essence: "the monad, the singularity". In the user's words: "I wanted the white circle on the orb to behave like an eye and also be centered in the deformation caused by the orb focusing on the cursor", "every state action should morph from this single white point", "the same point that is looking around when idle". Rules:
- **One point, made of the dots that already exist.** The monad is the existing cluster of cream-white dots at the lit core of the sphere (a small group of a few dots across), not a new shape. In the user's words: "its not something new, its reusing this" and "its not something drawn separately". It is the same dots of the same grid, lit cream. It is present in every state, including error and reduced motion. When it moves, the cream lighting moves across the grid, so different dots become the monad; no disc or overlay is drawn on top.
- **It is the eye.** In idle, the gaze moves the cream cluster itself, so the lit dots shift across the grid toward where it looks, not only as a parallax offset of the dense core. The point looks around inside the sphere, clamped so it never leaves it.
- **The deformation is centered on the point.** When the orb leans toward the pointer or a focused element, the dots bulge, gather and compress around the point's current position, so the point always sits at the center of the deformation and never off to one side.
- **Eye behaviors live in the cluster, expressed through which dots are lit:**
  - peering lights a few more dots;
  - a startle shrinks it to fewer dots;
  - a blink unlights its rows vertically, like a lid;
  - dozing narrows it to a dim line, half-closed;
  - waking opens it.
- **Every state morphs out of the point.** The point is the origin of every state's motion. The stagger is measured from the point's position, not the sphere's geometric center:
  - listening gathers dots toward it;
  - thinking swirls around it;
  - speaking emits ripples from it;
  - assembling throws dots and components out of it;
  - attention flares coral from it, and the attention line starts at it;
  - acting orbits it;
  - done blooms from it;
  - error makes it flicker and dim.
- **Transitions:** between states the point travels first and the dots follow from it outward, so every change reads as the singularity acting.

States and their life:
- **idle:** breath (±1.8% radius at 0.9 Hz), a ripple crossing the sphere, a limb wobble from simplex noise. The orb also acts like a curious pet (`gaze.ts`, tuned only by `GAZE_PERSONALITY`). Its monad (the cream cluster) moves across the grid toward the pointer or the keyboard-focused element (at most 50% of the radius, so it stays inside the sphere), and the dots gather, bulge and brighten around it while the outline stays round, with a lean of at most 3%. It moves on one under-damped spring, the only spring in the HUD that overshoots. It glances rather than locks: after 2 to 4 seconds on one spot it loses interest and drifts back to centre. After about a second on a spot it peers (the monad lights a few more dots and sits a little further, slightly brighter). A new notification or an opening overlay makes it glance there. A fast flick startles it (the sphere widens for 250ms). A jump to a far target makes it double-blink. After 60 seconds without input it dozes: slower breath, up to 20% dimmer, never coral, never jittering, and the phrase does not change, so dozing never reads as offline. Any input wakes it with a small perk-up. The gaze runs in the idle state only and never in another state. Reduced motion turns it off.
- **listening:** gathers 7% and leans toward the Ask field; a cream ring runs inward; tones run Ultraviolet at the limb to Orchid at the core.
- **thinking:** slow internal swirl (core one way, mid-depth the other) under a scanning light; the three tones swirl.
- **speaking:** pulses with the voice amplitude; a cream-cored waveform crosses the equator; ripples carry the tones.
- **assembling:** 9% of the dots are thrown out along their own spoke and pulled back; the rest tighten.
- **attention:** onset = core flare + a shockwave ring through the dots (1.3 s); hold = a faint coral ember (r < 0.17) breathing on a 2.2 s two-beat heart, a lean toward the slipping mark and a stream of coral dots to it; resolve = coral drains over about 2 s.
- **acting:** a working arc orbits the belt; one faint tilted orbit ring per running goal or workflow (max 3), each in its own tone.
- **done:** one bloom outward (10%), settling over a second.
- **error:** dim, flickering, jittering, a coral limb.
Reduced motion: one still frame of the sphere (attention = a faint static ember), the loop stops. The canvas pauses when off-screen or when the tab is hidden.

### Attention line (`shared/ui/hud/presence/LeaderLine.tsx`)
When something has slipped on the world view, a 1px coral line (35% base plus a 2px flowing dash, 2.2 s) runs from the orb core to the centre of the slipped mark (never its label), with a pulsing cap on the mark. It lives in a fixed SVG on the document body, is measured with `getBoundingClientRect` and updated through refs inside rAF on scroll, resize and layout change (no React render). The mark and its label pulse in sync through `--beat-offset` (the orb's absolute clock). Desktop only; phones pulse the row instead.

### The field chart (`hud/FieldChart.tsx`, signature)
"Time left × how sure." x = time left in bands: Slipped (−7d..now, coral hatch), a glowing NOW line, This week (0..7d), Later (7..30d, log), No deadline (a column at the right). y = confidence 0..1. Mark = claim kind (filled told/evidenced, half inferred, dashed suspected, hollow diamond goal); colour = state (coral slipped, dim suspected). A dotted trail above a mark shows where confidence stood before evidence aged. Labels are px-true, placed right or left with collision avoidance and a 1px leader when displaced. Hover or focus shows a callout (title, state · kind · posture, sure · age · deadline); click or Enter selects and opens the readout below the chart. Legend under the chart: told · evidenced, inferred, suspected, goal, slipped, "dotted trail = sureness decayed as evidence aged".

### Honesty visuals (apply everywhere)
- **Told / evidenced:** filled mark, solid chip, full-height meter.
- **Inferred:** half-filled mark, dashed chip ("asked, not stated"), half-height meter, dashed sparkline.
- **Suspected:** dashed hollow mark, dim colour, dashed module frame, shown as a question ("Confirm?") with Yes, track it / Drop.
- **Goal:** hollow rotated square.
- **Slipped:** coral mark, coral label, coral tick, coral module frame.
- **Decay:** the sparkline falls and the readout shows "▾0.05"; the chart trail is dotted; evidence age is printed ("3d ago").
- **Fixtures and gaps:** a value the API does not expose is omitted, not faked; a seeded placeholder is named as such in a tooltip or omitted from numbers.

### Motion
- Easing `--ease-out: cubic-bezier(0.16, 1, 0.3, 1)`; control transitions 150ms; frame light 220ms; cascade entrance 620ms with 80ms stagger from the orb's position, scale 0.72 → 1, blur 6px → 0 on desktop (no blur on phones); exit 180ms; reflow `layout="position"` 350ms.
- Text decodes in from scrambled glyphs (520ms, left to right); numerals count up (650ms, cubic ease-out, written through a ref); hairlines draw on (700ms); hover sweeps (600ms).
- One heartbeat clock (2.2 s) shared by the orb, the leader tip, the mark and its label.
- Scroll must hold 60fps: no per-frame filters, no backdrop blur, no layout-property animation, canvases pause off-screen.
- Reduced motion: still orb, no pulses, instant cascades (opacity only), draw-on and sweep off, transitions 150ms.

## Do's and Don'ts

### Do:
- **Do** keep every claim's posture visible: glyph, chip and meter style must agree across the chart, rows and cards.
- **Do** use the four brightness levels on purpose; cream is for names and the one sentence, not for everything.
- **Do** make hover and focus visible as light on the frame (brackets to cream, inset edge brighter).
- **Do** render module labels as `h2.lbl`, keep touch targets at 44px, keep chart type px-true, and theme caret, selection, scrollbars and focus rings from the palette.
- **Do** print numbers in JetBrains Mono with tabular figures and show the value beside any meter.
- **Do** answer "what does Ze understand, and what is it doing about it?" on every view; lead with what needs the user.

### Don't:
- **Don't** use coral for selection, emphasis, gates or confirmations.
- **Don't** add drop shadows, backdrop blur, rounded corners, flat lavender fills, or purple glow pills.
- **Don't** put the dot grid outside the hero viewport, or add noise and scanline textures.
- **Don't** cut or crossfade the orb between states; every change is a spring morph of the same dots.
- **Don't** show raw enums (`awaiting_gate`, `user_declared`), raw tracebacks, or prototype asides ("in the real engine") to the user.
- **Don't** add a second accent, a fifth brightness level, a kicker above a heading, or a cinematic register.
