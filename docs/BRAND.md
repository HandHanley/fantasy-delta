# DELTA — Brand & Design System

> **Δ — the measured change. Proven value, not market noise.**
> *Better decisions. Longer advantage.*

Canonical reference for the DELTA mark, palette, type, and UI conventions.
Sections 1–4 are transcribed from the brand mark exploration (`delta-brand.html`).
Sections 5–9 document conventions that live in the product but were not in that
document — they are recorded here so they stop being tribal knowledge.
Sections 10–12 record the redesign (31 Oct – 1 Nov 2026): the three Looks, the component
sizes every section now follows, and where the colour tables live. **When a section is
built or rebuilt, it follows section 11. Anything that does not is a leftover, not a style.**

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
| `--fog-2` | `#748A9C` (was #5C7080 until 31 Oct 2026: it failed the 4.5 to 1 readability bar for small text on cards, 3.4 to 1; #748A9C reads 4.9 on `--panel`, 5.3 on `--ink`) |

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

**Direction without a call** (Oct 2026): when something went up or down but DELTA is not saying buy or sell,
use **sky for up / more** and **violet for down / less**, never emerald and coral. In use on the Scorecard
(scored more / less than projected), Role Changes (playing more / less) and the per-season EPA columns.
Emerald and coral there would read as a buy or sell call that does not exist.

In use since the redesign also on: Market Moves, Big Board rank moves (▲ ▼), the Power Rankings Market
column, the Comp × discount on drafted prospects (violet, "less") and the "more / less" tags on the
prospect sheet (Prod+, Prod−, SF+, TEP+, RB−).

**Players side by side** (Compare tab, 22 Oct 2026): player one `--cp-1` (`#2DD4BF`, a FIXED teal),
player two `--sky`, player three `--violet`. Never `--teal-br` for a data series: themes repaint it,
and on the Violet theme player one turned the same colour as player three (on Sky, the same as player
two). The row-leader box uses neutral `--cp-lead` / `--cp-lead-bd` for the same reason.

**Teams in a trade** (Trade Calc, 1 Nov 2026): the same set, extended. Team A `--cp-1`, B `--sky`,
C `--violet`, D `--fog` — on the page and in the share picture. They were emerald and topaz, which
read as buy and watch.

**Categories get no colour.** Position chips (QB / RB / WR / TE), NFL team chips, draft-round chips
and labelled numbers (Cap, Board, Age, Ath) are plain: `--fog` text on `--ink-2` with a `--line`
border. They used emerald, topaz and sky by category, which is decoration wearing a signal's colour.

**Tiers are the one exception, and only by score.** The DELTA Score ring and number (`dsColor()`),
production percentiles (Big Board dDOM / PPA) and prospect score bands keep their green → topaz →
coral tiers (Decision 1, 31 Oct 2026). A tier colour must follow a number DELTA computed; it never
marks a category, a state or a team.

**Team colours on Live** are data from the scores feed, set inline, never tokens. `teamColor()`
lifts a colour until it is visible on the dark page; it swaps to the team's alternate only when the
primary is black or grey — never to a white or silver alternate over a real colour (the Cardinals
are red, not white). Team colour is never used as text: it goes on borders, bars, bands and spines.

**Accent vs active.** A selected pill, tab or view uses the accent (`--teal-br` on `--teal-tint`),
never emerald — emerald on an active "My Roster" pill read as "buy my roster".

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
misaligns and reads as sloppy. **Names and labels never do** (1 Nov 2026): player names in a
table, section labels and chips are `--sans`. A name in the mono face was the clearest sign of a
section that had not been redesigned.

### Five sizes (redesign, 31 Oct 2026)

Every piece of text is one of five sizes. Twenty-odd sizes between 6.5px and 34px were in use before.

| Size | Use |
|---|---|
| **12px** | Small print: labels under a number, meta lines (position · team), chips, footnotes, column labels |
| **13px** | Body: rows, names in lists, pill and button labels, descriptions |
| **16px** | Titles: card and section titles, big names, the main button's label, numbers that lead a row |
| **20px** | Page title, team or player name heading a view, mid scores |
| **28px** | The one big number: a hero score, a DELTA Score in a sheet |

- On pages built from JS, `dlTypeScaleIn()` (engine) snaps text already drawn to the nearest step
  (`dlTypeStep`: ≤10.25 → 12, ≤14.5 → 13, ≤18.5 → 16, ≤23.5 → 20, else 28) and turns CSS small
  capitals into capitalised text. It is used on the player pages, both pop-ups and the Trade Calc and
  Mock Draft panels. New work sets the sizes in CSS directly.
- **Drawn graphics are exempt:** the score ring's numbers, chart labels inside SVG, the ⓘ icon.
- **Known exemption, shared with Rankings:** the Rankings and roster table cells keep the board's own
  scale (14px Δ, 12px cells and 9.5px column labels on phones, 10.5 / 9.5px Call pills). They move
  together or not at all.

### Title Case, written in the text

Headings, labels, buttons, tabs and chips are Title Case — and the capitals are **in the text**
("Value Today", "Ask About", "Live"), not produced by `text-transform`. Small capitals
(`text-transform:uppercase` with letter-spacing) are retired: they were the second clearest sign of an
old section. Sentences stay sentences.

---

## 7. UI conventions

- **No emoji.** Anywhere. Monochrome dingbats (`★ ☆ ⚠ ✓ ✕ ⇄ ♞ ◷ ■`) are the
  approved iconography: they inherit CSS color and never render as full-color
  glyphs on iOS. Prefer inline SVG for anything load-bearing.
- **Accent themes** may recolor chrome only (`--teal-br`, `--teal`, and their
  tints). Signal colors never change with the theme. **The corollary:** anything that
  identifies DATA (a player's colour, a series, a highlight that belongs to a row) must
  not use the accent tokens, because a theme will repaint it into something else on the
  page. Check a new data colour under all six themes before shipping (22 Oct 2026).
- **Tooltips** use `data-tip`. The hidden state must be `display:none`, not
  `visibility:hidden` — a hidden tooltip that still occupies layout overflows
  its table wrapper and spawns a phantom scrollbar.
- **Personalization is per-device** (localStorage): columns, sort orders, filters, tick boxes. These
  never sync; say so in the UI. **The two exceptions are the accent theme and the Look**, which sync
  across devices for a signed-in account (Decision 9, 31 Oct 2026; `delta-sync.js`, `user_state`).
- **No hex outside `:root`** (and the colour tables in section 12). Never build a tint by gluing an
  alpha onto a colour in JS (`'var(--emerald)' + '22'` is not CSS — the Big Board prospect sheet's
  boxes never drew because of it). Mix in CSS: `color-mix(in srgb, var(--x) 24%, var(--panel))`,
  with a plain token on the line before as the fallback.
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
same system, not yet filled in. The size floor rules it out of tabs, rows, and small chrome.
**Panel lockups are retired** (redesign step 2, 31 Oct 2026; Big Board 1 Nov): the section and
page title does that job, and the mark lives in the header and the bottom bar. The Transfer
Portal still carries one — a leftover until that page is rebuilt.

---

## 9. Asset locations

| Asset | Path |
|---|---|
| Header mark (solid, detail) | inline SVG, `index.html` / `player.html` |
| Outline mark | inline SVG, College panel in `index.html` |
| App icons | `icons/icon-192.png`, `icon-512.png`, `icon-512-maskable.png`, `apple-touch-icon.png` |
| Social preview | `og-image.png` (1200×630) |
| Full exploration | `delta-brand.html` |

---

## 10. The Looks (31 Oct 2026)

Settings → **Look: Classic, Glass, Daylight** (Decision 8). Stored in `delta_look`, synced for a
signed-in account, applied as `<html data-look="glass|daylight">` before first paint (Classic has no
attribute). Every page links `delta-looks.css`, which holds only token overrides and the handful of
rules a Look needs.

| | Classic | Glass | Daylight |
|---|---|---|---|
| Page (`--ink`) | `#0A0F1A` | `#070B13` with a soft accent glow | `#F2F4F7` |
| Cards (`--panel`) | `#111A28` | `rgba(26,34,50,.58)`, blurred where supported | `#FFFFFF` with a soft shadow |
| Edges (`--line`) | `#1E2A3A` | `rgba(255,255,255,.09)` | `#E3E7EC` |
| Text (`--paper` / `--fog` / `--fog-2`) | `#EAF0F4` / `#8CA0B3` / `#748A9C` | as Classic | `#0A0F1A` / `#4F5E6C` / `#5F6C79` |
| Card corners | 14px | 20px | 16px |

**Daylight needs darker partners** for every colour that appears as text, because the bright ones are
1.9 to 1 on white. Every one clears 4.5 to 1 by a page-wide contrast scan:

| Token | Dark Looks | Daylight |
|---|---|---|
| `--emerald` (buy) | `#10B981` | `#047857` |
| `--coral` (sell) | `#E05745` | `#B4382A` |
| `--topaz` (watch) | `#E0B34D` | `#946200` |
| `--sky` | `#6BB6E0` | `#1E6FA8` |
| `--violet` | `#9B8AF0` | `#6650D0` |
| `--cp-1` | `#2DD4BF` | `#0F766E` |
| Accent, Teal | `#2DD4BF` | `#0A6660` |
| Accent, Violet / Sky / Cobalt / Orchid / Slate | as `DL_THEMES` | `#5B48C2` / `#1A6496` / `#2F5FC4` / `#A8358F` / `#475569` |

- **A card joins the Looks by class**, in the two `:is(...)` card lists in `delta-looks.css` (one for
  Glass, one for Daylight). Classes only inside `:is()`: an id raises the whole rule's weight. Every
  redesigned section added its cards there (`.dl-md-card`, `.dl-lg-tc`, `.dl-cp-sec`, `.dl-pr-card`,
  `.g`, `.hero`, …).
- **Things that float** (sheets, menus, the settings panel, pop-ups) are frosted in Glass; a phone that
  cannot blur gets solid Classic cards, never unreadable glass.
- **Share pictures never change with the Look.** `dlImgTok()` / `dlImgColors()` read colours with
  `data-look` removed for that instant, so a picture is identical whoever made it.

---

## 11. Components (redesign rules, 1 Nov 2026)

Applied section by section to Trade Calc, Mock Draft, Ledger, Compare, Big Board, Roster (My Team) and
Live. The player page and both pop-ups follow the same sizes (redesign step 3).

| Part | Rule |
|---|---|
| **Card** | 14px corners, `--panel`, 1px `--line`. Inner boxes 10–14px |
| **Pill** (a choice: position, week, view, team, filter) | 36px tall, 18px corners, 13px / 700 text, 14px side padding. Off: `--fog` on `--ink-2`. On: accent text and border on `--teal-tint` |
| **Main button** (Start Draft, Open In Trade Calc, Close) | 48px tall, 14px corners, 16px label. Filled with the accent only where there is one per screen (Trade Calc, Mock Draft); **tinted** (`--teal-tint`, accent border) where it repeats down a list (Ledger, Compare, Trade Partners — Decision 12) |
| **Second buttons** (Share Link, Share Image) | 48px, 13px label, outlined, side by side under the main one |
| **Small action** (Refresh, Edit Players, How This Is Ranked) | A 36px pill |
| **Text box** | 44px tall, 14px corners, **16px text** (smaller and an iPhone zooms the page on tap and never zooms back); placeholder 13px |
| **Select menu** | 36px+, 16px text, for the same reason |
| **Tabs / segmented switch** | 36–44px buttons inside a 14px-cornered track |
| **Section title** | 16px / 800, `--paper`, Title Case. Page title 20px |
| **Label above a control** | 13px / 700, `--fog`, Title Case (was 9.5px small capitals) |
| **Chip** (a tag on a row) | 12px / 700, 8px corners |
| **Table names** | `--sans` / 600; position and team underneath on phones, not beside |
| **Phone layout** | Nothing scrolls the page sideways at 360px. A wide table may scroll inside its own box only with the name column pinned (Power Rankings) |
| **Bottom bar** | Hides while a text box has focus, so the keyboard cannot push it over search results (`delta-nav.js`) |

**Box score unit cards** (Live, 1 Nov 2026): a 3px team-colour top line and a band of the team colour
mixed into the card (`color-mix … 24%`) behind the column labels, with the unit name (Passing,
Rushing…) in the band's left corner. No separate heading above the card.

**Testing a section** (how each one was checked): 390, 360 and 1300 wide; Classic, Glass and Daylight;
every text size on the five steps; no small capitals; no sideways scroll; a page-wide contrast scan
(4.5 to 1 for small text); the section's buttons clicked; no script errors.

---

## 12. The colour tables live in seven places

The accent themes are a table of six accents, each with a Daylight partner. Each page has to set its
accent **before the first paint** (otherwise it flashes teal), and that script runs before any shared
code exists, so it cannot read the real table. The table is therefore copied:

| Copy | Where |
|---|---|
| 1 | `DL_THEMES` / `DL_THEMES_DAY` in `index.html` (the real one, used by Settings) |
| 2–6 | The pre-paint scripts (`T` / `DAY`) in `index.html`, `player.html`, `cfb-player.html`, `privacy.html`, `terms.html` |
| 7 | The pre-paint script in `live.html` (added 1 Nov 2026 — Live had ignored the reader's accent) |

The six Settings swatch dots in `index.html` hardcode the same values once more. **Change one, change
all of them in the same commit.** A theme missing from a copy renders that whole page in teal, silently
— cobalt and orchid were missing from privacy and terms for months that way.

The Looks' token sheet (`delta-looks.css`) is the other place hex is allowed outside `:root`.

### Still to come (1 Nov 2026)

Sections built before the redesign and not yet rebuilt to section 11: Market, Rankings (the table's
own scale, above), Role Changes, Scorecard, College Rankings, College Role Changes, Transfer Portal
and the Watchlist. They already have the navigation, the Looks and the accent; their insides do not
yet follow the five sizes or Title Case.
