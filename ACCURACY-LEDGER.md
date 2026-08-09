# DELTA Accuracy Ledger — methodology

**Status:** pre-registered, written August 2026, before any 2026 outcomes were observed.
**Freeze target:** Sunday 6 September 2026 — before any Week 1 game is played.
**Two resolution dates, because the three tests resolve on different clocks:**
February 2027 (projections and rankings, against actual 2026 production) and
the Sunday before Week 1 2027 (pricing calls, against the 2027 market).

This document is the pre-registration. It exists so that the metrics are fixed
*before* the results are known, for the same reason NULL-RESULTS.md exists: the
pressure to reinterpret a measurement is strongest exactly when the measurement
is unflattering.

---

## 1. What DELTA actually claims

Three different numbers come out of the engine, and they make three different
claims. Grading them together produces mush, so the ledger keeps them apart.

| Number | Code path | Uses market data? | The claim |
|---|---|---|---|
| **DELTA Score** (`ds`, 0–99) | `calcDynastyScore` | **No** | This player's demonstrated dynasty profile is stronger than that player's |
| **Projected PPG** (`proj`) | `calcProj` | **No** (except rookies) | This player will average roughly this many points per game |
| **Model value** (`mv`) | `mvAsset` | **Yes, by design** | Given where the market prices this player, the profile justifies more/less |

This distinction is load-bearing and easy to misremember, so state it plainly:

* `calcDynastyScore` and its four axis functions (`dsAge`, `dsProduction`,
  `dsOpportunity`, `dsContract`) contain **no market reference at all**. The
  rankings table sorts on `dsScore`. The ordering users see is entirely DELTA's.
* `calcProj` builds from a games-weighted average of the player's own prior
  three seasons, then applies age curve, delta stack and injury factor. No
  market input. The one exception is rookies with no NFL history, who have no
  production to build from and take a market-anchored path.
* `mvAssetRaw` returns `market_value × age_curve × (1 + mvDelta) × injury`. The
  code comment is explicit: *"Model value: additive delta on market value."*
  This is deliberate. The verdict asks whether a player's **price** is justified
  by his profile, and you cannot grade a price without knowing it.

**Consequence for the gap.** Because `mv` is anchored to market, the market
value largely cancels in `gap = mv/mkt − 1`. The gap therefore measures whether
DELTA's multiplier stack on a player runs above or below the median multiplier
it applies across the whole pool. That is a real and gradeable signal, but it is
NOT two independent valuations colliding. Do not describe it as such.

**Consequence for honesty.** The claim "DELTA never uses market consensus" is
true of the score and the projection, and false of model value. Say so publicly
rather than letting someone discover it.

---

## 2. The three tests

### Test 1 — Projection accuracy (market-blind)

Frozen `proj` vs actual 2026 PPG.

* **MAE** (mean absolute error): average absolute miss, in points per game.
  Primary metric. Directly comparable to the published figures the industry
  reports for ESPN, CBS, FantasyPros et al.
* **RMSE** as a secondary metric. RMSE squares errors first, so it punishes
  single catastrophic misses far harder. Reported alongside MAE because the
  *difference* between them is informative: MAE ≪ RMSE means accuracy is being
  driven by a few disasters rather than broad bias.
* **Split by position.** Aggregate numbers hide systematic bias, and
  position-level bias is the only kind that is actionable.

Reported **twice**:

1. **Unconditional** — every graded player, including those who missed the season.
2. **Conditional on playing** — minimum 6 games. Answers "was the per-game rate
   right for the games he played", separated from "was he available".

Both are legitimate questions. Reporting only the first lets one torn PCL
contaminate the read on whether the rate model works. Players known to be out
*before* the freeze are excluded entirely (section 4); this split concerns
injuries that happen during the season, which nobody knew at freeze time.

### Test 2 — Ranking accuracy (market-blind)

Frozen `ds` ordering vs actual production ordering, within position, by rank
correlation (Spearman).

The most robust of the three. A season-ending injury moves one player rather
than distorting the whole list, so this degrades gracefully where MAE does not.

Also report **top-N hit rate** (did the frozen top 12 / top 24 at each position
finish top 12 / 24), because it is the form most readers actually understand.

### Test 3 — Pricing calls (market-relative)

Frozen `verdict` and `gap` vs where the market ends up.

**Graded in prices, not points.** A sell on a 28-year-old with an expiring
contract is not a prediction that he will play badly — it is a claim that his
price will fall. He may have an excellent season and still have been the correct
sell. Grading sells against production measures the wrong thing.

Primary measure: **change in positional market rank** for players tagged buy
vs players tagged sell. Rank rather than raw value, because raw FantasyCalc
values drift as the pool changes (picks convert to players, veterans retire) —
rank is immune to that drift.

This is a genuine out-of-sample test despite `mv` being market-anchored, because
the *frozen* market values are fixed and the future market is not yet observed.

---

## 3. What gets frozen

`scripts/freeze-snapshot.js` writes `data/freeze-2026.json`, and copies the
market grid to `data/freeze-2026-market.json`. Between them:

* Per player: `pos`, `t`, `mv`, `mkt`, `gap`, `verdict`, `ds`, `proj`,
  `rankMv`, `rankMk`, `style`.
* `scarcity_curve` — the SCAR_CURVE in force at freeze time.
* `engine_sha` — the git commit of the engine that produced these numbers.
* The **full market grid** (all 8 league-size × QB-format settings), copied from
  `data/market-values.json`, which is otherwise overwritten nightly and lost.

The last three exist so the snapshot is **reconstructable**. Without the curve
and the commit, a number in the ledger cannot be explained later, only reported.
Without the full grid, the ledger is permanently locked to the 12-SF basis.

**Basis:** computed and displayed at the 12-team superflex, half-PPR TE-premium
anchor — the same basis the verdict engine uses. Because projections, the
scarcity curve and the full market grid are all frozen, any other basis can be
recomputed exactly later. Basis is a *rendering* choice, not a commitment.

---

## 4. Exclusions

Excluded from the graded set, listed by name in the snapshot for transparency:

* **`mktStale`** — market value unreliable at snapshot time.
* **No market value** — nothing to compare against.
* **Known-out before freeze** (`excluded_known_out`) — players already ruled out
  for the season at freeze time.

The third deserves explanation. If a player is known to be out and DELTA
projects him near zero, he will "hit" that projection trivially, and including
him **inflates apparent accuracy**. This is not a prediction the model made; it
is information anyone had. Excluding them keeps the headline number honest.
They remain in the snapshot, flagged, so the decision is auditable.

---

## 5. Rules

1. **The frozen file is immutable.** Once written, it is never edited, never
   regenerated, never "corrected". If it is wrong, it is wrong, and the ledger
   records that DELTA was wrong. That is the entire point.
2. **The live model is not the ledger.** Updating the frozen record after the
   fact is look-ahead contamination and destroys the only thing the ledger is
   for. Two artifacts, opposite rules. Note this does NOT mean the live model
   chases every piece of news — section 6 defines exactly what it responds to,
   and the answer is deliberately narrow.
3. **Metrics are fixed by this document.** Adding a metric after seeing results
   requires recording that it was added post hoc, and why.
4. **Year one is not a verdict.** Ten years of published industry comparisons
   find no consistent year-over-year accuracy among individual projection
   sources — the leader rotates, and a simple average of all sources often beats
   an accuracy-weighted one. A single season is mostly noise. Frame the first
   ledger as opening the books; the signal is in the trend across three years.

---

## 6. In-season policy — what moves and what does not

Decided August 2026, before the pilot season. The governing principle:

> **Facts move slowly, situation moves as it happens, prices move daily.**

| Quantity | Moves in-season? | Why |
|---|---|---|
| **DELTA Score** | Essentially no | Claims *demonstrated* dynasty value. A demonstration is a completed season; three weeks of games is noise. Caveat below. |
| **Projected PPG** | Only for confirmed season-enders | Forward-looking by definition, but see the ripple decision below. |
| **Model value** | Yes, daily | It is market × DELTA's multipliers, and the market reprices nightly. |
| **Game logs** | Yes, weekly | Descriptive. They inform the reader; they do not feed the model. |

**Why weekly stats change nothing in the model.** This is deliberate, not a gap.
`SEASONS` in the stats pipeline is pinned to completed seasons, so 2026 results
never reach `ppg`, `games`, or anything derived from them until the offseason
roll. If a player has three big games and his market value jumps while his DELTA
Score holds, **that divergence is the signal** — it is the buy/sell mechanism
working in-season. A score that chased box scores would say nothing the market
had not already said louder.

**Caveat on the DELTA Score.** It is not perfectly static: contracts refresh
nightly and `dsContract` is 10% of the score, so a mid-season extension nudges
it. Accepted deliberately — it is a fact about the player and the effect is
small — but "the DELTA Score does not change in-season" is an approximation,
not a guarantee.

### The availability line

Two problems that look like one, separated because their risk profiles differ:

**The injured player himself — automated, visual.** Sleeper carries
`injury_status` and it is fetched nightly already. A player showing a normal
projection while on IR reads as a broken tool, and users would be right. So the
IR/OUT tag is automatic and visible.

**Zeroing a projection — manual only.** IR does **not** mean out for the season.
NFL rules permit return from IR and designated-to-return is routine; a Week 3
placement can be back by Week 8. Automating "IR → projection 0" would print
false zeros on players who come back. Projections are zeroed only for confirmed
season-enders (surgery announced, placed on season-ending reserve), by hand, via
`data/injury-overrides.json`.

**Teammate ripples — not in the pilot season.** When a starter goes down, his
teammates' opportunity genuinely changes. But one missed game, IR with a return
designation, and a torn ACL are different magnitudes, and none of them has been
calibrated for partial seasons. DELTA's own research bar is ≥2% RMSE improvement
with permutation p<0.05, and nothing here can clear that before Week 1. Shipping
uncalibrated magnitudes would be precisely the failure NULL-RESULTS.md exists to
prevent. In-season ripples stay manual and pre-freeze only.

**Instrument now, act later.** Sleeper injury-status transitions are logged
nightly with no action taken on them during 2026. Next offseason that log is the
dataset in-season ripple magnitudes can be calibrated against, instead of
starting from nothing.

### One reason for restraint specific to the pilot

The ledger grades *frozen* projections. Every post-freeze change to the live
model widens the gap between what DELTA said and what DELTA is showing. Keeping
that gap small in year one means the results can be reported without asterisks.
Pre-freeze changes are free — they land in the frozen record. Post-freeze changes
cost interpretability. This reason expires once the mechanism has one clean
season behind it.

---

## 7. Timeline

| When | What |
|---|---|
| Sun 6 Sep 2026 | Run the freeze, before any Week 1 game. Verify, then never touch again. |
| February 2027 | **Tests 1 and 2 resolve here.** Actual 2026 production now exists, so MAE, RMSE and ranking accuracy are final — not a preview. |
| Sunday before Week 1, 2027 | **Test 3 resolves here.** Second market snapshot; the pricing calls are graded. |
| Sunday before Week 1, 2028 / 2029 | Repeat the pricing test. The dynasty window is 2–3 years; a thesis can be right and take that long to pay. |

Why the two dates differ: a projection is graded against **points**, which exist
once the season ends. A buy/sell call is graded against **prices**, which need a
full year to move and are only comparable at the same point in the seasonal
cycle — after the rookie class has repriced the market, not mid-hype in January.

Note the 2027 date is the *Sunday before Week 1*, not a fixed calendar date, so
both readings sit at the same point in the cycle.

Freeze-to-freeze (September to September) rather than calendar year, so both
readings sit at the same point in the seasonal cycle — after the rookie class
has repriced the market, not in the middle of post-season hype.
