# DESIGN.md — CarbonPilot

The design system an agent should read before building any UI in this repo.
Drop-in convention: a coding agent reads `AGENTS.md` to know **how to build**, and this file to
know **how it should look**. If a change contradicts this document, either the change is wrong
or this document needs a deliberate edit — not a quiet drift.

---

## 1. Visual theme and atmosphere

**Print, not glass.** The product is an audit-grade carbon ledger: numbers that a sustainability
lead has to defend in front of a CFO. It should read like a statement from an accountant who is
good at their job — precise, calm, high-contrast, unornamented.

It should NOT read like an AI developer tool. That look is: a void-black canvas, a neon accent
used on every interactive element, glassy translucent cards, glowing gradients, everything
rounded. That exact aesthetic is catalogued as the *VoltAgent* house style in
`VoltAgent/awesome-design-md` — it is the single most common generated-UI look, and a judge has
seen it four times before lunch.

Two rules generate almost every decision below:

1. **Rules, not cards.** Structure comes from hairlines and full-bleed bands. There is no
   elevation scale, no shadow, no blur, no translucency. If you reach for a card, ask whether a
   rule and a band would do it — it almost always would.
2. **One accent per meaning.** Colour is only ever *state*: saved, flagged, stopped. There is no
   brand hue, so nothing is coloured for decoration and nothing is coloured "because the metric
   is good".

Density is medium-high and calm. Air comes from consistent spacing and generous leading, not
from empty space inside boxes.

---

## 2. Colour palette and roles

Every token lives in `tailwind.config.ts`. Do not introduce a hex value outside it.

| Token | Hex | Role |
|---|---|---|
| `paper` | `#fbfaf7` | Page canvas. Warm off-white, never pure white (pure white is `paper-panel`). |
| `paper-band` | `#f6f5f1` | Secondary band: sidebar, footnote strips, expanded evidence. |
| `paper-panel` | `#ffffff` | The only raised surface. Used sparingly — inputs, the command bar, memo blocks. |
| `ink` | `#14150f` | Primary text. Near-black with a green cast. Never `#000`. |
| `ink-soft` | `#33332e` | Serif body copy and the recorded series stroke. |
| `ink-muted` | `#6d6d63` | Secondary text, table figures, captions. |
| `ink-faint` | `#9a9a8e` | Kickers, axis ticks, tertiary metadata. |
| `rule` | `#e2e0d8` | Every hairline. This is the workhorse of the whole system. |
| `rule-strong` | `#c9c6ba` | Emphasis rules, form borders, empty-state outlines. |
| `save` | `#1c4b36` | Deep green. **Only** for a reduction or a completed state. |
| `alert` | `#9c5a12` | Burnt amber. **Only** for a flagged signal or medium effort. |
| `stop` | `#8f2f22` | Deep red. **Only** for an error or high severity. |
| `bar` | `#d6d3c8` | Neutral fill for the third segment of a stacked split. |

Notes that matter:
- There is no `sky`, no `mint`, no `lime`, no `rose`. If you want one, you are decorating.
- Opacity modifiers are acceptable for *state* tints only (`border-save/50`), never for surfaces.
- No gradients anywhere. A single audit found two radial glows on `body`; both are gone.

---

## 3. Typography

Three families, self-hosted via `next/font/google` in `app/layout.tsx` (never a runtime CDN link —
a judge's wifi is not a dependency we accept).

| Voice | Family | Variable | Job |
|---|---|---|---|
| Statement | **Source Serif 4** | `--font-serif` | Mastheads, band titles, editorial claims, figures in prose. |
| Explanation | **Inter** | `--font-sans` | Body copy, labels, controls, table category names. |
| Measurement | **IBM Plex Mono** | `--font-mono` | Every figure, every kicker, every axis tick. Always `tabular-nums`. |

The split is semantic, not stylistic: **serif states, sans explains, mono measures.** A number
rendered in the sans family is a bug.

Scale in use:

| Role | Size | Class |
|---|---|---|
| Masthead `h1` | 26px serif semibold | `font-serif text-[26px] font-semibold leading-none tracking-tight` |
| Hero figure | 46px mono medium | `fig text-[46px] font-medium leading-none tracking-[-0.02em]` |
| Band title `h2` | 17px serif semibold | via `SectionHead` |
| Editorial claim | 19px serif, leading 1.55 | `font-serif text-[19px] leading-[1.55]` |
| Body | 12.5–13.5px sans, leading 1.8 | `text-[13px] leading-relaxed` |
| Kicker | 10px mono uppercase, tracking .14em | `.kicker` |
| Table figure | 12.5px mono tabular | `.ledger tbody td` |

Sentence case for titles and buttons. Uppercase is reserved for `.kicker` and table headers.

---

## 4. Structure and components

Defined once in `app/globals.css` under `@layer components`. Use these; do not re-derive them.

- **`.kicker`** — the 10px mono uppercase label that opens every band. Always sits above a title.
- **`.band` / `.band-strong`** — a hairline or a 2px rule above a section. This is how the page is
  divided. A band plus a `SectionHead` replaces what used to be a card.
- **`.panel` / `.panel-pad`** — a flat white surface with a 1px rule and a 2px radius. The only
  raised element. Use it for the command bar, a memo, a drop zone — not for every block.
- **`.ledger`** — the table. First column is a label (sans, left-aligned). Every other column is
  mono, `tabular-nums`, right-aligned, so figures can be compared vertically without reading.
  Header cells are 9.5px mono uppercase in `ink-faint`.
- **`.footnote`** — the provenance strip. Real content, not decoration: method, sources, and the
  uncertainty that applies. Styled with a top rule and a `paper-band` fill.
- **`.chip`** — 10.5px mono, square-cornered, hairline border. Status only.
- **`.btn-primary`** — solid `ink` fill, `paper` text, 2px radius. One per view.
- **`.btn-ghost`** — hairline border, no fill. The default for secondary actions.
- **`.btn-quiet`** — underlined text link at 12px. For tertiary actions inside a band.
- **`SectionHead`** (`components/ui.tsx`) — kicker + serif title + optional right-aligned note and
  action. Every band opens with one.
- **`Stat`** — kicker + mono figure + sub-line. Deliberately not a card, so it can sit in a ruled
  row or a table cell.
- **`Footnote`** — wraps the provenance strip.
- **`Skeleton`** — flat `rule`-coloured block, no radius, no colour pulse.

Radii are set globally to 2–4px. `rounded-full` is reserved for status dots and nothing else.

---

## 5. Composition by surface

Each page has one archetype. Do not compose a Monitor surface like a landing page — that was the
original defect (a marketing hero on an operations dashboard).

- **Dashboard — Monitor.** Density and glanceability. Opens with a masthead rule, then one
  *statement band*: the headline finding as a serif sentence with the figures inside it, the
  annualised total beside it in tabular mono, and the scope split as a single stacked bar. Then
  bands: command bar, trend / breakdown, signals / ranked actions, provenance footnote. No hero
  panel, no four-up stat-card grid.
- **AI Insights — Monitor + Inspect.** Opens with the count of anomalies as a serif sentence in
  the masthead. Signals are ruled rows that expand into an audit trail. The full anomaly table is
  a `.ledger`. Method goes in the footnote.
- **Simulator — Configure, then Compare.** Sliders on the left with mono readouts; the projection
  on the right as a ruled stack, not a boxed card. Constraint-search results are a `.ledger` table
  because a set of scenarios is a comparison, and comparisons want aligned columns.
- **Action Plan — Operate.** A ranked register: rank and weighted score lead (mono), impacts
  align right, the owner select and create button sit on a ruled action line. Export controls live
  in the band's `SectionHead` action slot.
- **Upload — Configure.** Map first, calculate second. The drop zone is a dashed hairline
  rectangle. Both preview tables are `.ledger`. Nothing is written until the operator has seen the
  interpretation.

---

## 6. Depth and elevation

There is none, deliberately. Depth is expressed as: hairline `rule` < `rule-strong` < a 2px `ink`
masthead rule. No `box-shadow`, no `backdrop-blur`, no translucency, no gradients. A modal or
popover, should one be added, earns elevation with a rule and a `paper-panel` fill — not a shadow.

---

## 7. Do's and don'ts

**Do**
- Open every band with a `SectionHead` (kicker + serif title).
- Render every figure with `.fig` — mono, tabular, right-aligned.
- Use colour only for state, and pick the token that matches the *meaning*, not the mood.
- Write the finding as a sentence where a statement is the right form (Diagnose, Decide).
- Put provenance in a `.footnote`, with the uncertainty attached to the number it affects.
- Let data drive the copy: the dashboard's headline sentence is composed from `breakdown[0]` and
  the top anomaly, never hardcoded.

**Don't**
- Don't add a card to group things. Use a rule and spacing.
- Don't reintroduce a brand accent, a gradient, or a glow.
- Don't use pure white as the page background, or pure black as text.
- Don't use Inter for a number, or mono for prose.
- Don't centre body copy. Only genuinely empty states may centre; default to left.
- Don't invent a metric for a mockup. If a number appears, it came from the API.
- Don't fill a control with the page colour. A range thumb filled `paper` sitting on a `paper`
  page is invisible — only a 1px border separated it from the background. Any control that carries
  state must be legible against the surface it sits on, and must show its current value (the
  slider track fills in `ink` up to its own position via `--fill`).
- Don't keep a component alive with no consumer. A 7-colour category bar chart was deleted when a
  `.ledger` table replaced it, rather than left behind as dead code.

---

## 8. Slop diagnostic — re-run this after any large UI change

Score the build against these and fix anything that fires. A generated UI typically scores 6/10.

| # | Tell | Fires if |
|---|---|---|
| 1 | Tech gradient | Any gradient, or a coloured radial glow on a background. |
| 2 | Generic tech hue | Neon/emerald/sky accent on near-black, i.e. the default AI-devtool palette. |
| 3 | Feature-tile grid | Three or four equal cards with an icon, a heading and a sentence. |
| 4 | Accent rail | A saturated vertical bar on a card edge as the only hierarchy. |
| 5 | Unearned blur | Glassmorphism, or any blur with no elevation system behind it. |
| 6 | Monument stat | An oversized number with no compositional reason to be that size. |
| 7 | Icon topper | A rounded icon square above every card title. |
| 8 | Centre stack | Centred text and a symmetrical column as the default layout. |
| 9 | Default type | Inter (or system) used unchosen, at default weights and word-spacing. |
| 10 | Wrong surface | A landing-page composition on a Monitor/Operate surface. |

When this was last run against CarbonPilot, tells **1, 2, 5, 6, 9, 10** all fired. Root cause was
#10; the rest were symptoms. The fix was a composition change, not a repaint.

---

## 9. Responsive behaviour

- Sidebar (`Nav`) is `lg:` only; below that the app is single-column.
- Every band that is a two-column grid collapses to one column below `lg` (`900px`). Rules become
  top borders when a vertical divider would disappear.
- Ledger tables that would overflow get an `overflow-x-auto` wrapper. Do not hide columns.
- Touch targets in the mobile range are ≥ 32px; the mono readouts keep their size because they
  carry the meaning.

---

## 10. Agent prompt guide

Quick reference for a fresh agent:

```
Canvas #fbfaf7 · band #f6f5f1 · panel #ffffff
Ink #14150f · soft #33332e · muted #6d6d63 · faint #9a9a8e
Rules #e2e0d8 / #c9c6ba
State: save #1c4b36 · alert #9c5a12 · stop #8f2f22
Type: Source Serif 4 (states) · Inter (explains) · IBM Plex Mono (measures)
Radius 2px · no shadow · no blur · no gradient · no brand hue
```

A usable prompt: *"Add a <feature> to <page> using the CarbonPilot design system in DESIGN.md.
Open the band with a SectionHead, render figures with .fig in a .ledger table, and use colour only
for state. Do not add cards, gradients or a brand accent."*

Before you call it done, re-read section 7 and re-run section 8.
