# PRE-REGISTRATION — Own Value Scale: Draft-Day Rookie Values Learn From Past Misses

**Drafted:** 12 November 2026. **Status: LOCKED 12 Nov 2026 as a measured layer (amendment A1); MEASURED (§10), not yet in the weekly build.** The
2% test's crash failed (§6). Steve, 12 Nov: "I agree with your assumption that it's
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

**A1 (12 Nov, after the crash test failed, before any real run).** Steve chose option 1: "Im good with option 1." This
replaces §3's test with a measured layer, built the way Contract Security was (`PREREG-contract-security.md`):

- **Two places, measured separately** (full PPR, measured lines QB24 / RB34 / WR48 / TE14, the display build; half PPR
  + TE premium is reported):
  - **Draft day:** the offseason value's incoming-rookie rows (§1), t = 2004–2022. This sets Stage 2 pick values and
    the preseason value.
  - **In season, no game yet:** the in-season value's "this season ignored" rookie rows (`ovs_in_season` frame Sb,
    kind R0, week 9, pool ≤ t − 4), t = 2006–2022. The weekly build uses these for first-year players who haven't
    played.
- **Per draft range b** (§2's five): r = Σ w × outcome ÷ Σ w × value over that place's rows, with
  w = 0.5^((2026 − t) / 8), recency measured from today, as live matching does. d = r − 1.
- **Uncertainty:** 2,000 resamples of rows within each season (seed 20261112). se = the resamples' standard deviation of
  d, and the 95% range is their 2.5th–97.5th percentiles.
- **Shrunk:** d* = d × max(0, 1 − se² ÷ d²), as Contract Security.
- **Applied** only where the 95% range of d excludes 0. Otherwise the factor is 1. **Factor = 1 + d*.**
- **Reported:**
  - each factor with its range;
  - the rolling version (§2) for each class, to show how stable the factors are;
  - what changes: first-year players with no game in this week's build, and Stage 2 picks for the 2026 class.

## 10. Results (12 November 2026, A1 Measurement)

`study/ovs_rookie_layer.py`, `study/out/ovs_rookie_layer_{draft,inseason}.json`. Full PPR, measured lines.

| NFL Picks | Draft Day: Produced ÷ Value | Range Of d | Factor | No Game Yet (In Season): Produced ÷ Value | Range Of d | Factor |
|---|---|---|---|---|---|---|
| 1–12 | 1.78 | +0.41 to +1.15 | **×1.73** | 1.68 | +0.32 to +1.06 | **×1.63** |
| 13–32 | 1.47 | +0.11 to +0.89 | **×1.39** | 1.33 | −0.07 to +0.74 | ×1.00 (unclear) |
| 33–64 | 1.30 | +0.04 to +0.59 | **×1.23** | 1.43 | +0.13 to +0.78 | **×1.36** |
| 65–100 | 1.26 | −0.09 to +0.64 | ×1.00 (unclear) | 1.14 | −0.18 to +0.49 | ×1.00 (unclear) |
| 101+ | 1.29 | −0.13 to +0.75 | ×1.00 (unclear) | 0.69 | −0.49 to −0.12 | **×0.72** |

**What it changes, this week's build (first-year players with no game yet only; nobody else moves):**

- Fernando Mendoza 5,374 → 8,757 (31st → 4th).
- De'Zhaun Stribling 2,430 → 3,312 (71st → 58th).
- Max Klare 973 → 1,326.
- Ty Simpson unchanged at 4,199. He was pick 13, in the 13–32 range, where the in-season measurement wasn't clear
  enough.
- Day 3 and undrafted rookies who haven't played fall 28% (Jarquez Hunter 861 → 619).

**Two flags for Steve before this goes into the weekly build:**

1. **A cliff at pick 12/13 (in season)** and a non-monotone order (13–32 ×1.00 between ×1.63 and ×1.36). Both come
   from the "apply only where the range excludes zero" rule meeting noisy ranges, not from anything real. Pick 12 gets
   ×1.63 and pick 13 gets ×1.00.
2. **Mendoza 4th overall from draft slot alone.** It follows the measured rule (top-12 picks produced 1.68× their
   in-season "no game" value), but it's a big call on one cameo game.

**Stage 2 picks:** the class-strength version (`PLAN-pick-values-now.md` §7) is barely moved by this layer, because the
same factors apply to the class and to history and mostly cancel. Sorting the calibrated 2026 class directly still
falls below Stage 1 from the Late 1st on (for example, 2nd Mid 776 vs 1,546), so the class-strength version is still
the better Stage 2.
