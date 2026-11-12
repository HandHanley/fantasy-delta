# PLAN — Rookie Picks On Today's New Value Scale

**Drafted:** 12 November 2026, before any outcome on today's scale was computed. **Status: METHOD FIXED; measurement
follows.** Steve, 12 Nov: "let's do 1 and 2 now", and on a flat discount: "I do not think all 2027 picks should be
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
  (`ovs_in_season.outcomes`). Missed seasons count as zero. A player who changed position uses his position each
  season.
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
