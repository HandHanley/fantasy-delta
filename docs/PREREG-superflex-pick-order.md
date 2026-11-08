# PRE-REGISTRATION — A Superflex Rookie-Draft Order From Scarcity Math

**Drafted:** 7 November 2026. **Status: LOCKED 7 Nov 2026 (Steve's OK).** Locked by committing this
document with `study/pick_values_sf.py` before the confirmatory run. Changes after that are amendments (§10).

Follows `docs/PREREG-pick-values-formats.md` (run 7 Nov). There, in every superflex format, quarterback picks came out
2.9–4.7× underpriced, because the only long rookie-draft history (FFC, 2014–2023) comes from 1QB leagues, where
quarterbacks go later. This builds a superflex order with math instead of borrowing anyone's rankings.

---

## Plain-English Summary (For Steve)

1. **Redo each past rookie draft as superflex.** Every rookie's expected value is what his 1QB draft spot usually
   produces; quarterbacks get multiplied by a boost. Re-sort. Running backs, receivers and tight ends keep their
   order; quarterbacks move up.
2. **How big a boost?** Set from how real superflex drafters actually move QBs up: the boost whose order best matches
   DynastyProcess's real superflex rookie rankings in 2020 and 2021. (The pure scarcity math gave 3.4–3.7×, which put
   Josh Rosen ahead of Saquon Barkley in 2018; see A1.) The draft order is always about what drafters do — FFC's 1QB
   order already is — so this borrows drafter behaviour for the order only. Every pick's value still comes from what
   the players actually produced.
3. **Price picks from the new order**, with the same fairness check and fix as every other format.
4. **Check it on years the fit never saw** (2022 and 2023): our order must match real superflex rankings better than
   the 1QB order does, in both years. It compares orders only, not how anyone turned out.

**If the reality check passes**, these become the superflex pick values. **If it fails**, we keep today's superflex
values with the 1QB-order warning.

## 1. The Quarterback Boost

**One boost for every class and every superflex format**, fitted once in DELTA's format: try every boost from 1.00 to
4.00 in steps of 0.05; for each, build the order (§2) for the 2020 and 2021 classes and take the average rank
correlation with DynastyProcess's superflex rookie rankings (mid-May `value_2qb`, `dp_superflex_slots` unchanged) over
rookies in both lists. The best wins; ties go to the smaller boost. Recorded in `study/out/pick_values_sf_fit.json`.
RB, WR and TE boosts are exactly 1.

**Reported, deciding nothing:** the scarcity-math boost per format and class, `(QB veterans' five-season value under
that format's superflex lines) ÷ (same QBs, same seasons, 1QB lines)` over snapshots finished before the class.

## 2. The Superflex Order

- **The board:** every QB/RB/WR/TE in FFC's rookie file for the class (32–46 players), matched to NFL records by
  `scripts/future-first-study.py`'s own rules, not cut at 36.
- **A rookie's expected value** = the average 1QB-line value of players taken in his 1QB slot range in the **other**
  classes (slot ranges 1–4, 5–8, 9–12, 13–24, 25–36; slots past 36 use 25–36), × the boost if he's a quarterback.
  Classes 2014–2021 use the other seven; 2022–2023 (reality check only) use all eight.
- **Re-sort** by expected value, ties kept in 1QB order. The top 36 are the superflex slots.
- **Leak check (asserted):** changing a class's own outcomes leaves its order unchanged.

## 3. Pick Values

For each of the 18 superflex formats, `docs/PREREG-pick-values.md`'s method on the new order: tier values from the
superflex slots (leave one class out), matched veterans, R and its 95% range from 4,000 resamples, and the fix always
applied (formats amendment A1). Priced by pick number in the same five slot ranges.

## 4. Reality Check On Unseen Years (Decides)

DELTA's format, classes **2022 and 2023** (never used by the fit), against DynastyProcess's superflex rookie rankings:
- For each class, the rank correlation between our order and DynastyProcess's, over rookies in both; the same for
  FFC's 1QB order.
- **Pass:** our order's correlation is higher than the 1QB order's in **both** classes.

Reported, deciding nothing: the average slot of the class's top two QBs in each order (are real superflex drafters
taking QBs earlier or later than our math?), and each class's correlations.

## 5. Crash Tests, Before Lock

- **Fairness check on the new order:** the same worlds as before (`test_pick_values_formats.py`), on DELTA's format and
  the shallowest superflex format (10-team standard, no TE premium), 100 runs, 1,000 resamples. Bars: fair ≥ 90%,
  30% tilt caught ≥ 80%. Under the "always apply" rule, a power failure is reported, not a stop.
- **Order sanity, on the real data:** the fitted boost is above 1 and QBs move up on average.

## 6. Reported, Deciding Nothing

The boost per class; QB picks' R in the new order (expected to fall toward 1); slot values by format.

## 7. Limits, Stated Now

- **Assumes drafters follow value.** If real superflex drafters reach for QBs beyond the math, real picks yield less
  than our values; the reality check's QB-slot comparison shows the direction.
- **QBs the 1QB drafters skipped don't exist on our board.** In real superflex drafts some go in rounds 2–3.
- **A QB's 1QB value is his slot's average.** In 1QB formats QB picks came out priced about like everyone else (formats
  study: QB ×0.97–1.52 vs the rest ×1.28–1.58), which supports this, roughly.
- **Small numbers:** 33 QBs among the 279 graded picks; four classes in the reality check. May rankings (after the NFL
  draft) vs FFC's late-summer mocks.

## 8. What Each Result Allows (Steve's OK Needed)

| Result | What It Allows |
|---|---|
| Reality check passes | Superflex pick values from this order replace the formats study's superflex rows |
| Reality check fails | Keep the formats study's superflex rows, with the 1QB-order warning |

## 9. Not Licensed Here

1QB formats (unchanged), class strength, landing spot, anything after the NFL draft.

## 10. Amendments

**Before lock**
- **A1 (7 Nov).** The first draft used the pure scarcity-math boost. On the real data it came out at 3.4–3.7× (DELTA's
  format) and put all four 2018 first-round QBs ahead of Saquon Barkley, Josh Rosen at 4 — an order no real superflex
  draft produced. A second idea, measuring rookie QBs directly by 1QB draft spot, was too thin: 8–11 QBs per group,
  and QBs taken 13th–24th averaged more than first-rounders (215 vs 154), on a couple of hits. Both looks used only the
  2018 class's order. Replaced by one boost fitted to real superflex rookie order on 2020–2021 and checked on
  2022–2023 (§1, §4); the scarcity boost is still reported. Also, the crash-test sanity rule ("boost above 1, QBs move
  up") now applies to the fitted boost.
- **The fit (7 Nov, `study/out/pick_values_sf_fit.json`):** boost **1.90**. Average correlation with real superflex
  order on 2020–2021: 0.935, against 0.868 at boost 1.00 (the 1QB order). The fit is loose: every boost from 1.85 to
  3.25 scores within 0.004 of the best. 2018 under 1.90: Barkley 1, Mayfield 5, Lamar Jackson 10, Darnold 11,
  Rosen 12. No 2022–2023 comparison has been computed.
- **Crash tests on the fitted order (7 Nov, `study/out/pick_values_sf_crash.json`, 100 runs, 1,000 resamples):**

| Format | Fair World: Range Included 1.0 (Bar 90) | 30% Tilt: Caught (Bar 80) | QBs Move Up (Average Slots) |
|---|---|---|---|
| 12-team Superflex Half PPR TE Premium | 100 of 100 | 88 of 100 | 10.1 |
| 10-team Superflex Standard | 100 of 100 | 84 of 100 | 7.3 |

  **PASS**, and order sanity passed. (A first crash run on the scarcity-math order also passed, 97 and 92 of 100; it
  was superseded by A1.) The sanity code checks the scarcity boost is above 1; the fitted boost (1.90) is too.

## 11. Results (7 Nov 2026, Run Once)

`study/out/pick_values_sf_results.json`. Boost 1.90 (fitted, §1).

**The reality check passed (§4): our superflex order matched real superflex rookie rankings better than the 1QB order
in both unseen years.** So by §8 these replace the formats study's superflex rows.

| Class | Rookies Compared | Our Order vs Real Superflex | 1QB Order vs Real Superflex | Top Two QBs' Average Slot (Ours / 1QB / Real) |
|---|---|---|---|---|
| 2022 | 31 | 0.976 | 0.898 | 9.5 / 19.0 / 11.5 |
| 2023 | 32 | 0.952 | 0.924 | 1.5 / 7.5 / 3.5 |

Our order takes the top QBs about two slots *earlier* than real superflex rankings did, so real drafters are not
reaching beyond the math; if anything the reverse (§7's worry ran the other way).

**Pick values (each format's fix applied; each format's own ruler):**

| Format | Fix (R) | 95% Range | Slots 1–4 | 5–8 | 9–12 | 13–24 | 25–36 | Before (1QB Order), 1–4 / 5–8 / 9–12 |
|---|---|---|---|---|---|---|---|---|
| 10-team Superflex Standard | ×1.47 | 1.10–1.80 | 7,314 | 5,664 | 5,321 | 2,250 | 1,476 | 7,497 / 5,004 / 3,888 |
| 10-team Superflex Standard TE Premium | ×1.51 | 1.10–1.83 | 7,500 | 5,823 | 5,463 | 2,331 | 1,519 | 7,240 / 4,823 / 3,816 |
| 10-team Superflex Half PPR | ×1.44 | 1.13–1.97 | 7,379 | 6,099 | 5,110 | 2,329 | 1,493 | 8,066 / 5,357 / 4,126 |
| 10-team Superflex Half PPR TE Premium | ×1.57 | 1.17–2.02 | 8,041 | 6,666 | 5,571 | 2,570 | 1,640 | 8,010 / 5,308 / 4,153 |
| 10-team Superflex Full PPR | ×1.52 | 1.18–2.02 | 7,278 | 5,939 | 5,302 | 2,360 | 1,500 | 7,392 / 4,997 / 3,731 |
| 10-team Superflex Full PPR TE Premium | ×1.58 | 1.19–2.01 | 7,529 | 6,270 | 5,389 | 2,418 | 1,629 | 7,581 / 5,110 / 3,873 |
| 12-team Superflex Standard | ×1.39 | 1.11–1.71 | 6,465 | 4,883 | 4,888 | 1,955 | 1,413 | 6,610 / 4,520 / 3,697 |
| 12-team Superflex Standard TE Premium | ×1.42 | 1.13–1.72 | 6,611 | 5,495 | 4,500 | 2,178 | 1,281 | 6,618 / 4,516 / 3,718 |
| 12-team Superflex Half PPR | ×1.52 | 1.12–1.80 | 7,594 | 6,386 | 5,366 | 2,570 | 1,531 | 7,047 / 4,878 / 3,872 |
| 12-team Superflex Half PPR TE Premium | ×1.61 | 1.15–1.83 | 8,083 | 6,817 | 5,725 | 2,779 | 1,654 | 7,368 / 5,088 / 4,105 |
| 12-team Superflex Full PPR | ×1.33 | 1.13–1.87 | 6,930 | 5,706 | 5,357 | 2,437 | 1,497 | 7,244 / 5,152 / 3,994 |
| 12-team Superflex Full PPR TE Premium | ×1.47 | 1.11–1.79 | 7,620 | 6,582 | 5,609 | 2,965 | 1,391 | 7,557 / 5,359 / 4,209 |
| 14-team Superflex Standard | ×1.27 | 1.08–1.64 | 5,605 | 4,142 | 4,416 | 1,854 | 1,066 | 6,224 / 4,234 / 3,904 |
| 14-team Superflex Standard TE Premium | ×1.26 | 1.09–1.62 | 5,574 | 4,242 | 4,296 | 1,875 | 1,077 | 6,004 / 4,066 / 3,806 |
| 14-team Superflex Half PPR | ×1.31 | 1.10–1.63 | 6,141 | 4,796 | 4,873 | 2,121 | 1,276 | 6,554 / 4,649 / 4,069 |
| 14-team Superflex Half PPR TE Premium | ×1.41 | 1.10–1.63 | 6,627 | 5,195 | 5,262 | 2,534 | 1,147 | 6,497 / 4,595 / 4,063 |
| 14-team Superflex Full PPR | ×1.37 | 1.11–1.66 | 6,916 | 5,665 | 5,521 | 2,710 | 1,311 | 6,760 / 4,900 / 4,138 |
| 14-team Superflex Full PPR TE Premium | ×1.43 | 1.11–1.67 | 6,896 | 6,264 | 5,774 | 2,877 | 1,388 | 6,844 / 4,952 / 4,237 |

**QB picks:** underpricing fell from ×2.86–4.70 (1QB order) to ×1.62–2.27. Better, not gone: even in
a superflex order, rookie QBs went on to produce more than their draft spot's average.

**Mid and Late 1st rise, 2nd and 3rd mostly fall:** quarterbacks now sit in the first round, so the first round is worth more.

**Out of order in 5 formats:** slots 9–12 come out slightly above 5–8 (12-team Superflex Standard, 14-team Superflex Standard, 14-team Superflex Standard TE Premium, 14-team Superflex Half PPR, 14-team Superflex Half PPR TE Premium). Each range holds 32 picks,
so this is noise; a calculator can't show a Late 1st above a Mid 1st. How to smooth it is Steve's call (not decided here).

**What it allows (Steve's OK needed):** these superflex values in the Trade Calc in place of the 1QB-order ones; the
1QB formats keep the formats study's values.
