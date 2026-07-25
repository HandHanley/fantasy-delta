# DELTA — Brand & Design System

> **Δ — the measured change. Proven value, not market noise.**
> *Better decisions. Longer advantage.*

Canonical reference for the DELTA mark, palette, type, and UI conventions.
Sections 1–4 are transcribed from the brand mark exploration (`delta-brand.html`).
Sections 5–9 document conventions that live in the product but were not in that
document — they are recorded here so they stop being tribal knowledge.

---

## 1. The mark

One mark, two readings. The internal axis is a set of yard lines and a precision
scale at the same time — the product's thesis, drawn.

| Element | Meaning |
|---|---|
| **Delta triangle** | Δ means change. Pointing up: growth, advantage, ascent — and the literal shape of the name. |
| **Graduated axis** | Hash marks widening toward the base read as field yard lines *and* a measurement scale — precision, the range opening up. |
| **Two-facet fold** | Lit plane and shadow plane give depth without a heavy 3D render — dimensional, still flat enough to scale. |

### Geometry (128×128 viewBox)

```
Left facet   M64 22 L24 106 L64 106 Z
Right facet  M64 22 L64 106 L104 106 Z
Full outline M64 22 L24 106 L104 106 Z
Fold axis    x=64, y 25→106 (solid) | y 32→102 (outline)
Hash marks   y=52 (x 58→70) · y=70 (x 55→73) · y=88 (x 52→76)
```

Never redraw by hand — copy the coordinates.

---

## 2. Two finishes

Same silhouette, two treatments.

### Solid
Two-facet fill, lit and shadow planes. Reads boldest and survives the smallest sizes.
**Use for:** favicon · app icon · dense UI

### Outline
Same silhouette, hollowed. The stroke carries the teal-to-emerald switch with a
brushed metallic core.
**Use for:** hero · watermark · merch · **≥ 40px**

```
outer stroke  url(#oStroke)  width 7.5
core stroke   url(#oCore)    width 2.3, opacity 0.5
glow filter   feDropShadow stdDeviation 3, #2DD4BF @ 0.35
```

---

## 3. Two tiers by size

Same outer silhouette in both, so they register as one brand — only the interior
detail changes with scale.

| Tier | Contains | Use at |
|---|---|---|
| **Detail Mark** | Facets, fold highlight, graduated hash axis | headers · loading · marketing · **≥ 32px** |
| **Mini Mark** | Silhouette, two-facet gradient, faint fold | favicon · app icon · avatars · **≤ 32px** |

Below ~32px the detail mark swaps to the mini mark so the silhouette never turns
to mush. At 16px the fold and gradient still read as a delta, because the mini
mark drops everything that would blur.

**App icon:** mini mark on ink, in the platform squircle. A hairline keeps it
defined on light home screens.

---

## 4. Rules — do not break

- **Clearspace of one triangle-width (X) on every side.**
- **Never recolor the gradient.**
- **Never rotate the mark.**
- **Never add an outline to the detail version.**

### Lockups
- **Horizontal** — headers
- **Stacked** — tight columns
- **Mark as "A"** — the mark standing in for the A in DELTA, when the wordmark
  should carry the whole idea

---

## 5. Palette

### Brand gradient
The established teal-to-emerald on near-black. The gradient runs light (lit facet)
to deep (shadow facet).

| Token | Hex | Role |
|---|---|---|
| Teal Bright | `#2DD4BF` | lit facet, primary chrome accent |
| Teal | `#14B8A6` | gradient mid |
| Emerald | `#10B981` | gradient step |
| Emerald Deep | `#047857` | shadow facet |
| Mint | `#CCFBF1` | the axis and hash marks only |
| Ink | `#0A0F1A` | ground |

### Surfaces & text
| Token | Hex |
|---|---|
| `--ink` | `#0A0F1A` |
| `--ink-2` | `#0D1420` |
| `--panel` | `#111A28` |
| `--line` | `#1E2A3A` |
| `--paper` | `#EAF0F4` |
| `--fog` | `#8CA0B3` |
| `--fog-2` | `#5C7080` |

### Signal colors — reserved, never decorative
These carry meaning everywhere in the product. **Do not reuse them for chrome,
themes, categories, or decoration** — doing so invents a signal that isn't there.

| Token | Hex | Means |
|---|---|---|
| `--emerald` | `#10B981` | **buy** |
| `--coral` | `#E05745` | **sell** |
| `--topaz` | `#E0B34D` | **watch** / caution / watchlist star |

### Support hues — categorical, not signals
| Token | Hex | Use |
|---|---|---|
| `--sky` | `#6BB6E0` | information, comparison-B, draft-eligibility highlight |
| `--violet` | `#9B8AF0` | chart series |

### Tints
Low-alpha versions so chips sit correctly on `--ink`:
`--emerald-tint` `--coral-tint` `--topaz-tint` `--teal-tint` `--teal-soft`
`--sky-tint` `--violet-tint` `--row-hi`

---

## 6. Typography

| Token | Stack | Use |
|---|---|---|
| `--sans` | Nunito Sans → Avenir Next → system-ui | all body copy, labels, UI |
| `--mono` | SFMono-Regular → ui-monospace → JetBrains Mono | **all figures** — tabular numerals keep columns aligned |
| `--geo` | Century Gothic → Futura → Questrial → Josefin Sans | wordmark and display only |

Loaded weights: Nunito Sans 400/600/700/800 · JetBrains Mono 400/500/700 ·
Josefin Sans 600/700.

**Numbers always use `--mono`.** A ranking table with proportional figures
misaligns and reads as sloppy.

---

## 7. UI conventions

- **No emoji.** Anywhere. Monochrome dingbats (`★ ☆ ⚠ ✓ ✕ ⇄ ♞ ◷ ■`) are the
  approved iconography: they inherit CSS color and never render as full-color
  glyphs on iOS. Prefer inline SVG for anything load-bearing.
- **Accent themes** may recolor chrome only (`--teal-br`, `--teal`, and their
  tints). Signal colors never change with the theme.
- **Tooltips** use `data-tip`. The hidden state must be `display:none`, not
  `visibility:hidden` — a hidden tooltip that still occupies layout overflows
  its table wrapper and spawns a phantom scrollbar.
- **Personalization is per-device** (localStorage). Nothing syncs; say so in the UI.
- **Brightness carries meaning before hue does.** Dimmed = secondary or not-yet-
  relevant; bright = active. This survives a colorblind reader and a bad screen.

---

## 8. NFL vs College

Both are DELTA — same silhouette, so they register as one brand.

| | NFL | College |
|---|---|---|
| Mark finish | **Solid** | **Outline** (hero, ≥40px) |
| Scored | DELTA Score (0–99) | **Never** — production facts only |

The outline's lighter, instrument-like read is the visual note for college: the
same system, not yet filled in. It appears as a hero at the top of the College
panel only — the size floor rules it out of tabs, rows, and small chrome.

---

## 9. Asset locations

| Asset | Path |
|---|---|
| Header mark (solid, detail) | inline SVG, `index.html` / `player.html` |
| Outline mark | inline SVG, College panel in `index.html` |
| App icons | `icons/icon-192.png`, `icon-512.png`, `icon-512-maskable.png`, `apple-touch-icon.png` |
| Social preview | `og-image.png` (1200×630) |
| Full exploration | `delta-brand.html` |
