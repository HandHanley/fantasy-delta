# PLAN — Rookie Picks On Today's New Value Scale

**Drafted:** 12 November 2026, before any outcome on today's scale was computed. **Status: STAGE 1 MEASURED 12 Nov (§6); STAGE 2
REVISION PROPOSED (§7), awaiting Steve.** Steve, 12 Nov: "let's do 1 and 2 now", and on a flat discount: "I do not think all 2027 picks should be
worth less than an already-drafted rookie … we need to figure out an informed way to price these".

Builds on `PREREG-pick-values.md`, `PREREG-pick-values-formats.md` and `PREREG-superflex-pick-order.md` (all locked and
run on 7 Nov, on the old ruler).

---

## Plain-English Summary (For Steve)

**No time discount.** New Value counts the next three seasons: 2027, 2028 and 2029. A 2027 rookie's first three
seasons are the same three, so a 2027 pick and a current rookie are measured on the same years.

**Stage 1, now until the NFL draft.** A pick is worth what the rookie taken at that spot went on to produce over his
first three seasons. That's measured over the 2014–2023 rookie drafts, as a smooth curve from 1.01 to 3.12.

**Stage 2, after the NFL draft.** The class is known, so the 1.01 is worth DELTA's incoming-rookie value of the
class's best rookie, the 1.02 the second best, and so on.

## 1. Stage 1: The Slot Curve

- **Which rookie went where:** the locked superflex rookie-draft order. That's Fantasy Football Calculator's 1QB rookie
  ADP, re-sorted with the fitted QB boost of 1.9 (`pick_values_sf.py`, `board()` and `sf_order()`), slots 1–36,
  classes 2014–2023. The order's inputs are the locked ones for 12-team superflex, full PPR (`one_qb` lines, FV5);
  only the outcome below is new.
- **Outcome (today's scale):** what he produced over his first three seasons (`cls` to `cls + 2`), full PPR, above the
  measured starter lines QB24 / RB34 / WR48 / TE14. It uses the 0.9 yearly weight, exactly as New Value's own outcome
  (`ovs_in_season.outcomes`), on his rookie position line, as New Value's outcome uses the row's position. Missed
  seasons count as zero. (Corrected before running: the draft said "his position each season", which New Value doesn't
  do.)
- **The curve:** a decreasing best fit (isotonic regression) of outcome on slot, over all 360 picks. A later pick is
  never worth more than an earlier one. The curve is flat wherever the data can't tell slots apart, so it doesn't
  invent a difference between, say, the 2.05 and the 2.06.
- **Range:** 2,000 resamples (picks resampled within each class), seed 20261112. Reported, deciding nothing.
- **On the scale:** value = 10,000 × slot outcome ÷ the weekly build's top raw value (this week Jaxon Smith-Njigba's),
  the same division every player gets. Pick values move with the ruler each week, as players' do.
- **Board names:** Early / Mid / Late 1st = the average of slots 1–4, 5–8 and 9–12. The 2nd round is 13–16, 17–20 and
  21–24, and the 3rd is 25–28, 29–32 and 33–36. Once the order is set, a pick takes its own slot.

## 2. No Fairness Multiplier (Changed From 7 Nov, With The Reason)

The 7 Nov method multiplied picks by R (×1.33 for 12-team superflex full PPR), so that a pick and a veteran priced alike
produced alike. On today's scale, drafted rookies who haven't played (Ty Simpson, Carson Beck) are already valued
without any multiplier. A pick multiplied by R would jump down by about a quarter the day it becomes a drafted rookie.
So picks are priced like drafted rookies, with no R, and the question moves to the whole scale. At week 9, rookies
produced 93% of their value and veterans 81% (`PREREG-ovs-small-samples.md` §10). That points the same way R did, and
is an open calibration question for the scale, not for picks alone.

## 3. Stage 2: After The NFL Draft

- **When:** draft-pick data exists for the class (nflverse `draft_picks` rows for that season).
- **The rule:** the class's drafted QB/RB/WR/TE rookies are valued with DELTA's incoming-rookie value (draft slot and
  age, the rule that values Ty Simpson today) and sorted. The k-th best takes slot k.
- **Known limit:** this assumes drafters follow DELTA's order. Real drafters don't always, which is why Stage 1 uses
  the real historical order.
- **Shown now as a check:** the 2026 class's values sorted the same way, beside Stage 1's curve. It shows what Stage 2
  would have said for this year's class.

## 4. Reported

- Each slot's raw average and the curve.
- Board-name values with ranges.
- The same with the old lines (QB24 / RB30 / WR42 / TE14), to show what the lines changed.
- Stage 2 for the 2026 class.
- Today's comparison: Denzel Boston (drafted 2026, valued from his games) against the 1.08.

## 5. Not Here

- **Class strength before the NFL draft** (college production) is a separate test (`PREREG-pick-class-strength.md`,
  to be drafted).
- **Other league formats:** this is 12-team superflex, full PPR only, the dev column's format.

## 6. Stage 1 Results (12 November 2026)

`study/pick_values_now.py`, `study/out/pick_values_now.json`.

- **Reproduction check:** the order and FV5 outcomes rebuilt the 7 Nov fairness R for this format exactly. 360 picks.
- **Scale:** this week's top raw value is 304.0 (Smith-Njigba).

| Pick | Value (Measured Lines) | 95% Range | Value (Old Lines) |
|---|---|---|---|
| Early 1st (1.01–1.04) | 5,280 | 4,118–6,863 | 4,738 |
| Mid 1st (1.05–1.08) | 3,513 | 2,738–4,485 | 3,024 |
| Late 1st (1.09–1.12) | 2,822 | 2,063–3,779 | 2,549 |
| Early 2nd | 2,401 | 1,542–3,117 | 2,086 |
| Mid 2nd | 1,546 | 943–2,322 | 1,333 |
| Late 2nd | 1,103 | 754–1,493 | 888 |
| Early 3rd | 955 | 642–1,315 | 740 |
| Mid 3rd | 807 | 467–1,134 | 636 |
| Late 3rd | 615 | 171–838 | 481 |

**Each slot (measured lines):** 1.01 6,687; 1.02–1.03 5,076; 1.04 4,279; 1.05 4,065; 1.06–1.07 3,430; 1.08–1.09 3,128;
1.10–1.11 2,859; 1.12 2,442; 2.01–2.04 about 2,400; 2.05–2.09 1,546; 2.10–3.04 955; 3.05–3.11 807; 3.12 38.

- **The 1.01s:** Manziel 0, Winston 132, Elliott 396, Fournette 181, Barkley 334, Murray 333, Edwards-Helaire 40,
  Lawrence 210, Hall 211, Stroud 196 (FV3).
- **Limit:** 3.12's 38 comes from ten picks that produced almost nothing. It's real, but one slot's average; treat it
  as about the 3.11's value.
- **Today's comparison:** Denzel Boston is 2,896 (62nd) and the 1.08 is 3,128. Close, with the pick a touch ahead.

## 7. Stage 2 Check Found A Level Gap, And A Proposed Fix

Sorting the 2026 class by DELTA's incoming-rookie value (`study/out/pick_values_stage2_2026.json`) gave values far
below Stage 1's from the 1.03 on. For example, slot 9 came out 1,708 (Ty Simpson) against 3,128. Over 2014–2023
(`out/pick_values_stage2_history.json`), the k-th best incoming-rookie value averages 0.6–0.8 of what the k-th
drafted rookie went on to produce.

- **Looked at, a known-results look at the adopted value:** incoming rookies in classes 2014–2022 produced 1.43× their
  draft-day value, 1.37× for the top 12, and 1.58× for NFL first-rounders. That is the same size as 7 Nov's R
  (1.33–1.39).
- **So DELTA's draft-day rookie values look about 40% low.** That's a calibration question for the whole scale, opened
  separately.
- **Stage 2 as written would drop every pick's value by about a third** the day the NFL draft happens.

**Proposed revision (Steve's call):** after the NFL draft, a pick keeps Stage 1's level, scaled by the class's
strength. For each board name (Early 1st, Mid 1st …), multiply Stage 1's value by the class's average incoming-rookie
value at those slots ÷ the 2014–2023 average at the same slots. The 2026 class as the example:

| Pick | Stage 1 | 2026 Class Strength | Stage 2 |
|---|---|---|---|
| Early 1st | 5,280 | ×1.45 | 7,666 |
| Mid 1st | 3,513 | ×1.00 | 3,527 |
| Late 1st | 2,822 | ×0.75 | 2,118 |
| Early 2nd | 2,401 | ×0.64 | 1,537 |
| Mid 2nd | 1,546 | ×0.65 | 1,005 |
| Late 2nd | 1,103 | ×0.80 | 879 |
| 3rd round | 955 / 807 / 615 | ×0.93–1.01 | 883 / 798 / 621 |

That's a top-heavy class (Love, Mendoza, Tate), then thin.

## 8. Wired In

`study/new_value_weekly.py` adds the next class's picks to `data/new-value.json` (board names and each slot), scaled
by the week's `top_raw`. They aren't shown on the site.
