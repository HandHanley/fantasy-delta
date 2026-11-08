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
