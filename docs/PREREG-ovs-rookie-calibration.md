# PRE-REGISTRATION — Own Value Scale: Draft-Day Rookie Values Learn From Past Misses

**Drafted:** 12 November 2026. **Status: DRAFT, NOT LOCKED. Crash test failed (§6); taken to Steve.** Steve, 12 Nov: "I agree with your assumption that it's
likely because today's rookies do historically produce more than older years. We should do that study." It locks by
committing this document with `study/ovs_rookie_calibration.py` and passing crash results, before the one real run.

---

## Plain-English Summary (For Steve)

**The problem.** On draft day, DELTA values a rookie from past rookies with a similar NFL draft slot and age. Over the
2009–2023 classes, rookies went on to produce about 1.4× those values.

**Two causes, found before this was written (§5):**

1. **The top of the draft gets mixed with later picks.** Nobody is picked earlier than 1st, so a top pick's 30
   comparables are mostly later picks. Picks 1–12 were matched to players averaging pick 18, and valued at 89 against
   159 produced.
2. **Rookies produce more now, as you guessed.** Top-12 picks averaged 102 over their first three seasons in 2003–07,
   and 165 in 2018–23. The comparables average about eight years older than the class being valued.

**The fix.** After matching, multiply each rookie's value by how far off DELTA's draft-day values were for his draft
range in past classes whose results are already in. The ranges are picks 1–12, 13–32, 33–64, 65–100, and 101 or later
(undrafted included). Only classes whose three seasons had finished by then count, with recent classes counting more.
Both causes get fixed at once, by DELTA's own track record.

**The test.** On 2014–2023 rookies, the fixed values must predict their first three seasons at least 2% better, with
the usual permutation check.

## 1. Frame And Rows

- **The adopted offseason value's incoming-rookie rows** (`ovs_era.setup`, kind R0): draft slot and age, 30 matches,
  recency weighting, pool ≤ t − 3, outcome FV3 over the first three seasons.
- **Study scoring:** half PPR + TE premium, the adopted lines (QB24 / RB34 / WR44 / TE18). Full PPR is reported.
- **Values for every incoming-rookie row t = 2004–2022** (classes 2005–2023). Each value is computed point-in-time,
  from its own pool.

## 2. The Calibration Factor

For a rookie in class c (row t = c − 1), in draft range b:

- f = Σ w × outcome ÷ Σ w × value, over rookies in range b from classes whose outcome windows closed by then (rows
  t′ ≤ t − 3);
- w = 0.5^((t − t′) / 8), the matching's own recency weight;
- **new value = value × f.**

Positions are pooled. No test row's own outcome, or any later class's, is read.

## 3. The Test

- **Rows:** incoming rookies, classes 2014–2023 (t = 2013–2022), with complete outcomes.
- **Decides:** typical miss (RMSE, FV3), new vs today, at least **2% better** with paired permutation p < 0.05
  (10,000 shuffles).
- **Passes →** draft-day rookie values (offseason value), and the in-season value for first-year players with no
  game, use the factor (Steve's OK). **Fails →** no change.

## 4. Reported

- Each range's factor over time.
- Produced ÷ value by range, today and new.
- By position.
- Full PPR.
- The 2026 class's values.
- Stage 2 pick values with the fix (`PLAN-pick-values-now.md` §7).

## 5. Prior Looks (Recorded Before Drafting)

On 12 Nov, on the adopted offseason value, full PPR, measured lines (`/tmp` diagnostics, numbers recorded here):

- **By class:** incoming rookies produced 1.43× their value in classes 2014–2022. By class, 2009–2023, the ratio ran
  1.0–2.2.
- **By draft range:**

| Picks | Rookies | Average Value | Average Produced | Average Pick Of His Matches |
|---|---|---|---|---|
| 1–12 | 70 | 88.8 | 158.7 | 18.2 |
| 13–32 | 73 | 53.6 | 75.9 | 38.2 |
| 33–64 | 150 | 42.0 | 54.3 | 58.3 |
| 65–100 | 164 | 25.0 | 34.0 | 92.7 |
| 101–160 | 284 | 11.1 | 11.3 | 139.1 |
| 161+ | 454 | 3.4 | 5.7 | 199.2 |

- **By position:** produced ÷ value QB 1.74, RB 1.35, WR 1.43, TE 1.19.
- **No calibrated value has been compared with any outcome.**

## 6. Crash Tests, Before Lock

- **Noise:** outcomes shuffled among incoming rookies within class and position, then values and factors rebuilt. It
  may pass at most 1 of 20.
- **Planted:** truth = today's value × (1.4, 1.4, 1.25, 1.25, 1.0) by range, set by hand, plus real misses shuffled
  within position. Factors are rebuilt from the planted truth. It must pass at least 80% of 200.

**Results (12 Nov, `study/out/ovs_rookie_calibration_crash.json`):**

- **Noise:** passed 0 of 20 (OK).
- **Planted:** passed **33 of 200 (16.5%)**, median lift 1.2%. **FAIL.**

**Why:** rookie outcomes swing so widely between hits and busts that even a planted 40% undervaluation of the top
picks moves the typical miss only about 1%. It's the same wall Contract Security hit (`POWER-contract-bump.md`): the
2% bar can't see a level correction. Taken to Steve before any real run.

**Options put to Steve:**

1. Measure the factors as a layer, the way Contract Security was adopted: a bootstrap range per draft range, shrunk
   toward 1 by its own uncertainty, applied where the range excludes 1.
2. Run the 2% test as written, expecting a fail.
3. Fix the top-of-draft matching itself. That hits the same power wall.

## 7. Limits

- **Five fixed ranges;** the factor is constant within a range.
- **Positions pooled.**
- **The factor learns from DELTA's own values,** so it would need re-measuring if rookie matching changed.

## 8. Not Licensed Here

The DELTA Score, the live site, buy/sell calls.

## 9. Amendments

None yet.
