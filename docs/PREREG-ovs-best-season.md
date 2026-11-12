# PRE-REGISTRATION — Own Value Scale: Best Season In Matching

**Drafted:** 12 November 2026. **Status: LOCKED 12 November 2026 as a MEASUREMENT ONLY (amendment A1). Nothing ships from it.** Steve, 12 Nov: "I'd
like to run the best season test first, and then I do want to look into QB-play angle as well after".

---

## Plain-English Summary (For Steve)

**The question.** Justin Jefferson is 80th because DELTA weighs his last three seasons (18.7, 11.9 and 13.6 points a
game), not his 2020–2023 peak. Would matching on "best season he's ever had" make DELTA more accurate?

**The change.** One new veteran matching feature: his best earlier full season, in the era-adjusted units production
already uses (8+ games; if none, any season with a game). If this season's production is higher, that counts as his best.
How much it counts (1.0, 1.5 or 3.0, against production's 3.0) is picked by history on 2006–2012 only.

**The test.** Week 9, 2013–2022. The new version must predict the next three seasons at least 2% better, p < 0.05, with
close trades no more than 1 point worse.

## 1. Details

- **Frame:** the adopted in-season value (`ovs_qb_starts.py` frame S): per available game, §7, §8, no games number.
- **Best season:** points per game ÷ that season's starter level at his position (the era rule), seasons before this
  one with 8+ games. A row's feature is the larger of that and his production number. A row with no earlier season
  (1,514 rows, mostly rookies) uses his production number.
- **Injury-neutral:** games count only to decide which seasons are full enough to be his best. Missed games never lower
  the number.
- **Equivalence, checked in code:** at weight 0 every match is identical to today's.
- **Unchanged:** everything else, including first-year QBs with no game (incoming-rookie value).

## 2–4. Picking, Test, Reported

- **Weight:** the lowest typical miss on fit rows 2006–2012 (4,355 rows), from {1.0, 1.5, 3.0}.
- **Decides:** test rows 2013–2022 (6,808), ≥ 2% better, paired permutation p < 0.05, trade guard.
- **Reported:** every weight on the test rows, by position, and produced ÷ value for former stars now 20%+ off their best,
  former-star WRs, and stars near their best. Also today's page with Jefferson.

## 5. Prior Looks (Recorded Before Drafting)

Steve and Claude looked at what groups produced ÷ today's value (week 9, 2013–2022):

- all veterans 81%;
- former stars (best season ≥ 1.1 × starter) now 20%+ off it: 86%;
- former-star WRs: 58%;
- former-star QBs: 113%.

The 8 closest Jefferson-like WR rows (Beckham 2019 and 2020, Michael Thomas 2020 and 2022, Josh Gordon 2015 and 2018,
Moss 2006, Boldin 2009) were listed with outcomes. No best-season value was compared with any outcome.

## 6. Crash Tests

**Results (12 Nov, `study/out/ovs_best_season_crash.json`):**

- **Noise:** passed 0 of 20 (OK).
- **Planted** (truth = today + 0.75 × (weight 1.5 − today), plus the real misses shuffled within position): passed
  **0 of 200**, median lift 0.8%. **FAIL.**

**Why:** the feature moves values a little for most players (about 4 points on an average of 25), so even if it were the
truth, overall accuracy would move about 1%, under the 2% bar.

**Checked, deciding nothing:** on former stars alone (505 test rows), the planted world passes 24.5% (weight 1.5) or 44%
(weight 3.0). Too few rows.

**Options put to Steve:**
1. Run it once as a measurement that decides nothing.
2. Skip to the QB-play angle.

## 7–9. Limits, Not Licensed, Amendments

- **Limits:** week 9 only; one weight for every position.
- **Not licensed:** the DELTA Score, the live site, buy/sell calls.
- **Amendments:**
  - **A1 (12 Nov, after the crash test failed, before any real run).** Steve: "yeah if we have it written, may as well
    run it to see." The run is a measurement only. It decides nothing, and no result can ship the feature. Everything
    else runs exactly as written. The "decision" field in the results file is ignored; the decision is no change.
