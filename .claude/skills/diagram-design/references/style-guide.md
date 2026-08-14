# Style Guide

**The single source of truth for colors, typography, and tokens.** Every diagram draws from this — not from hex values inlined in other reference files. If you want to change the visual skin of Schematic, change this file.

**Active skin: Ze / ze-web brand** (onboarded from `apps/ze-web/src/app/styles/globals.css` — the void-black, plum-voltage product UI). See "Custom tokens — Ze brand" below for the extraction rationale. The tables in this section now hold the Ze values, not the shipped defaults.

To regenerate from a different URL or source, see [`onboarding.md`](onboarding.md).

---

## Tokens

### Semantic roles

Every token is referred to by **semantic role**, not by its hex value. Type references (`type-*.md`) and SKILL.md say `accent`, not `#8052ff`.

| Role | Purpose | Light | Dark |
|---|---|---|---|
| `paper` | Page background, default node fill | `#f7f6f4` (warm-neutral bone) | `#000000` (void) |
| `paper-2` | Diagram container bg, secondary fill | `#efeeeb` | `#141414` |
| `ink` | Primary text, primary stroke | `#0a0a0a` (near-void) | `#ffffff` (bone) |
| `muted` | Secondary text, default arrow stroke | `#6b6b6b` (darkened smoke, AA-safe on light paper) | `#9a9a9a` (smoke) |
| `soft` | Sublabels, boundary labels | `#8a8a8a` | `#bdbdbd` (ash) |
| `rule` | Hairline borders | `rgba(10,10,10,0.12)` | `rgba(255,255,255,0.12)` |
| `rule-solid` | Stronger borders, baselines | `#bdbdbd` (ash) | `rgba(189,189,189,0.25)` |
| `accent` | Focal / 1–2 max per diagram | `#8052ff` (plum-voltage) | `#9a7bff` |
| `accent-tint` | Fill for accent-bordered boxes | `rgba(128,82,255,0.08)` | `rgba(128,82,255,0.14)` |
| `link` | HTTP/API calls, external arrows | `#2e5aa8` | `#6a95d8` |

> **Brand palette source:** `apps/ze-web/src/app/styles/globals.css` `@theme` block — `void #000000`, `bone #ffffff`, `ash #bdbdbd`, `smoke #9a9a9a`, `plum-voltage #8052ff` (the single UI accent → diagram `accent`), plus reserved state hues `amber-spark #ffb829` (warning), `lichen #15846e` (success), `ember #ef4444` (danger/destructive) which stay reserved for their app meaning and are **not** used decoratively in diagrams. Ze-web defines no brand blue, so `link` keeps the skill default (`#2e5aa8` / `#6a95d8`) — it's visually distinct from `accent` and reads as "external/HTTP" without colliding with plum-voltage's focal meaning.
>
> `paper` is kept warm-neutral-light by default (constraint: pure white is sterile) rather than void-black, since these diagrams embed as static images in Markdown docs read on both light and dark viewers; the **dark variant** goes to true `#000000` void to match the app exactly. `ink` on light is near-void `#0a0a0a` rather than a soft jet-black, since the brand has no muted-black token. `muted` is darkened from brand `smoke #9a9a9a` to `#6b6b6b` for light mode only — raw smoke fails WCAG AA on `#f7f6f4` paper; dark mode keeps true brand smoke, which passes AA on void.
>
> **Note:** The pre-baked example HTML files in `assets/` were built under the shipped default skin, not this one. Diagrams generated for the `ze` repo use the tokens above.

### Inversion rule (light → dark)

Any `rgba(28,25,23, X)` in light becomes `rgba(250,247,242, X)` in dark. Same opacities, RGB flipped. The accent gets a slight hue-shift brighter to read on dark paper.

### Series palette (multi-series chart types only)

A small set of desaturated, editorial-tone colors for chart types that genuinely need to distinguish multiple overlapping entities (currently: **radar**). The "1-focal" rule still holds — `accent` is reserved for the focal series; the palette below covers the rest.

| Token | Light | Dark | Notes |
|---|---|---|---|
| `series-1` | `#7c8f6f` (sage) | `#9caf8f` | Non-focal series |
| `series-2` | `#5e7a9b` (dusty-blue) | `#82a0c0` | Non-focal series |
| `series-3` | `#b8915a` (mustard) | `#d3ad7a` | Non-focal series |
| `series-4` | `#9c6b50` (rust-brown) | `#b88670` | Non-focal series |
| `series-5` | `#6e6479` (slate) | `#8d8298` | Non-focal series |

Fills sit at `0.18` opacity light, `0.22` dark; strokes use the full color. **Don't backfill these tokens to non-chart types** — architecture, swimlane, etc. continue to use muted-ink variants. The series palette is opt-in for diagrams where overlapping shapes demand distinguishable color, not a license to add color elsewhere.

### Terminal skin (opt-in alternate)

A self-contained palette for the terminal-window primitive (see [primitive-terminal.md](primitive-terminal.md)) — a CLI-chrome register for dev-tool posts and technical social cards. It does not replace the default skin above and isn't affected by onboarding; it's a second, fixed skin you opt into per-diagram.

| Token | Hex | Purpose |
|---|---|---|
| `terminal-page` | `#0a0a0a` | Page background behind the window |
| `terminal-paper` | `#141414` | Window body, node fill |
| `terminal-bar` | `#1b1b1b` | Titlebar strip |
| `terminal-border` | `#2b2b2b` | Window border, hairlines |
| `terminal-ink` | `#f5f5f5` | Primary text, primary stroke (same white-smoke as default `ink`) |
| `terminal-muted` | `#9a9a9a` | Secondary text, sublabels, ring stroke |
| `terminal-soft` | `#5c5c5c` | Tertiary — inactive dots, spokes |
| `terminal-accent` | `#ff5a36` | The one accent — focal station, prompt sign, active dot |
| `terminal-accent-tint` | `rgba(255,90,54,0.12)` | Fill for accent-bordered boxes |

**1-accent rule still holds.** Everything that isn't `terminal-ink` or `terminal-muted`/`terminal-soft` should be `terminal-accent` — never introduce a second hue.

---

## Typography

| Role | Family | Size | Weight | Usage |
|---|---|---|---|---|
| `title` | Instrument Serif | 1.75rem | 400 | Page H1 |
| `node-name` | Inter (sans) | 12px | 600 | Human-readable labels |
| `sublabel` | Geist Mono | 9px | 400 | Port, protocol, URL, field type |
| `eyebrow` | Geist Mono | 7–8px | 500, tracked 0.18em, uppercase | Type tags, axis labels |
| `arrow-label` | Geist Mono | 8px | 400, tracked 0.06em | Arrow annotations |
| `callout` | Instrument Serif *italic* | 14px | 400 | Editorial asides only |

> `node-name` is Inter — ze-web's product sans (`--font-sans: 'Inter', ui-sans-serif, system-ui, sans-serif` in `globals.css`) — so diagram labels visually match the app's own UI text. Ze-web defines no serif or mono family, so `title`/`callout` keep Instrument Serif and `sublabel`/`eyebrow`/`arrow-label` keep Geist Mono per the style guide's own constraint (§ Constraints: "keep Instrument Serif ... anyway — the contrast is load-bearing").

### Font stack

```html
<link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
```

**Load-bearing rule:** Mono is for *technical* content (ports, commands, URLs, field types). Names go in Inter sans. Page title is Instrument Serif. Italic Instrument Serif is reserved for annotation callouts (see [primitive-annotation.md](primitive-annotation.md)). **Never JetBrains Mono** as a blanket "dev" font.

---

## Stroke, radius, spacing

| Token | Value | Use |
|---|---|---|
| `stroke-thin` | `0.8` | Tag-box outlines, leaf nodes |
| `stroke-default` | `1` | Most strokes |
| `stroke-strong` | `1.2` | Emphasis strokes |
| `radius-sm` | `4` | Small tags |
| `radius-md` | `6` | Node boxes |
| `radius-lg` | `8` | Containers, rings |
| `grid` | `4` | Every coord, size, and gap is divisible by 4 (hard rule) |

---

## Node type → treatment

Semantic role combinations — reference these by name in type specs.

| Type | Fill | Stroke |
|---|---|---|
| `focal` (1–2 max) | `accent-tint` | `accent` |
| `backend` | `#ffffff` (white) | `ink` |
| `store` | `ink @ 0.05` | `muted` |
| `external` | `ink @ 0.03` | `ink @ 0.30` |
| `input` | `muted @ 0.10` | `soft` |
| `optional` | `ink @ 0.02` | `ink @ 0.20` dashed `4,3` |
| `security` | `accent @ 0.05` | `accent @ 0.50` dashed `4,4` |

---

## Customizing the skin

Three options:

1. **Run onboarding** — see [`onboarding.md`](onboarding.md). Drop a URL; the skill extracts the palette + fonts and rewrites this file.
2. **Edit by hand** — change the hex values in the tables above. Run the pre-output taste gate afterward to verify the accent still reads as "focal" against the new paper color.
3. **Brand handoff** — paste your existing design-token JSON into a new section here and map its tokens to the semantic roles above.

### Constraints (don't break these)

- **Contrast**: `ink` must hit WCAG AA on `paper`. `muted` must hit AA on `paper` for 11px+ text.
- **One accent**: pick one color for `accent`. Two accents erases the focal signal.
- **No rainbow palette**: if your brand ships 8 colors, pick 3 (paper, ink, accent). The rest become `muted` variants.
- **Serif + sans + mono**: three families, not more. If brand typography is all sans, keep Instrument Serif for `title` and `callout` anyway — the contrast is load-bearing.
- **Paper is warm-neutral, not pure white**: pure white turns the design sterile. Pick a cream, bone, or light grey with a hint of warmth.
- **Dot pattern is optional, not default**: the 22×22 dot pattern is an opt-in "dotted paper" variant (good for long-form editorial hero diagrams). The default background is a clean `paper` fill, no pattern. When the pattern is enabled, it should sit at ~10% opacity of `ink` on `paper` — visible but quiet.
- **Container is clean by default**: the diagram sits directly on the page paper, no secondary container background or border. A framed variant (`paper-2` bg + `rule` border + 8px radius + padding) is available as an opt-in for card-heavy layouts, but don't reach for it by default — the extra chrome fights the figure.
