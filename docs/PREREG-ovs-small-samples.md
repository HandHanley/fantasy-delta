# PRE-REGISTRATION — Own Value Scale: Don't Overreact To A Few Games

**Drafted:** 11 November 2026. **Status: LOCKED 12 November 2026** (Steve chose option 1 on injuries, 12 Nov: "Option 1
absolutely"). Crash tests passed (§6). Steve, 10 Nov eye test: Omar Cooper 47th on four games
("I could not trade Omar Cooper for … Breece Hall, Jonathan Taylor, De'Von Achane…"). 11 Nov: "let's go to 2. Small
sample sizes." It locks by committing this document with `study/ovs_small_samples.py` and passing crash results,
before the one real run.

---

## Plain-English Summary (For Steve)

**The problem.** In season, this season's points per game are the newest and heaviest part of a player's production.
Three games count as much as nine. A hot three-game start makes him look like the past players who did that over a
full half-season, and those players were mostly real. The 9 Nov study already showed the symptom: players with five or
fewer games went on to produce only 39% of their value.

**The fix.** Mix two values DELTA already computes:

- **This season counted:** today's in-season value.
- **This season ignored:** what DELTA said before the season. For a rookie, that's his draft-slot value.

The more games he's played this season, the more the first one counts. With K as the "trust" number:

| Games This Season | Weight On This Season (K = 4) |
|---|---|
| 1 | 20% |
| 3 | 43% |
| 6 | 60% |
| 9 | 69% |

**It works both ways.** A cold three-game start is pulled up toward his preseason value just as much as a hot one is
pulled down. It's about how much evidence there is, not about good or bad.

**Injuries (Steve's call before lock).** A player who missed weeks hurt has fewer games of evidence, so his start
counts less. The missed weeks never count against him: his value moves toward what DELTA thought before the season,
never below it because he was hurt.

**How K is picked, and the test.**

- **Picking K:** history picks it, from 1, 2, 4, 8 or 16, using only week-9 seasons 2006–2012.
- **The test:** on 2013–2022, the chosen K must predict the next three seasons at least 2% better than today, with the
  usual permutation check.

## 1. The Change, And Only The Change

- **Rows:** week 9, the adopted in-season value (`ovs_qb_starts.py` frame S), built the same way:
  - points per available game;
  - first-year QBs count only games played;
  - QB games by the Start Profile rule;
  - a first-year QB with no game takes his incoming-rookie value;
  - no games feature.
- **Two values per row, both already built:**
  - **In:** today's in-season value.
  - **Base:** the baseline frame `Sb`, this season ignored (`ovs_in_season.build`), matched with the same machinery. A
    rookie's baseline is his incoming-rookie value (kind R0).
- **n:** the games this season's production rests on, exactly the denominator `prod_available` uses. That is available
  games through week 9, with QB games by the Start Profile rule, and games played for a first-year QB.
- **Value:** n ÷ (n + K) × In + K ÷ (n + K) × Base. A row valued as an incoming rookie (n = 0) keeps its value.
- **n = 0 veterans** (no available game this season: every week hurt, suspended, holdout, retired, unsigned) take Base.
  The formula already says so; stated here because it's 2,301 of 11,163 rows (first-year QBs with no game included), nearly all with no future value.
- **n is captured, not re-derived:** the script runs `prod_available`'s own source with one line added to record the
  denominator, and asserts its production matches the real call exactly.
- **Everything else is unchanged:** outcomes (FV3), the 30 matches, the pool, recency weighting.

## 2. Picking K (Fit Seasons Only)

- **Fit rows:** week-9 rows with t = 2006–2012 (4,355 rows). Pools are thin early on: a 2006 row matches only from 2002,
  and 10 rows have fewer than 30 matches (fewest 11). In and Base are equally affected.
- **The grid:** K ∈ {1, 2, 4, 8, 16}. The K with the lowest typical miss (RMSE, FV3) on the fit rows is chosen.
- **No test season is read** to choose K.

## 3. The Test

- **Rows:** week 9, 2013–2022, the same rows as the 9 Nov studies.
- **Decides:** typical miss, chosen K vs today's in-season value. It must be at least **2% better**, with paired
  permutation p < 0.05 (a player's rows together, 10,000 shuffles).
- **Guard:** close synthetic trades no more than 1.0 point worse.
- **Passes →** the in-season value uses the mix (Steve's OK). **Fails →** no change.

## 4. Reported, Deciding Nothing

- **Every K on the test rows:** this shows whether the choice was lucky.
- **By position.**
- **Groups, as what they produced ÷ value, today and with the mix:**
  - rookies;
  - 5 or fewer games, never hurt (the "does he have a job" rows);
  - 2+ weeks out hurt;
  - veterans with no game this season;
  - healthy veterans with 6+ games (should barely move).
  - The out-hurt group shows how injured players move: they should land near healthy-comparables levels, not below
    them.
- **Today's page (week 9, 2026):** Omar Cooper, Antonio Williams, Caleb Douglas, Jaxson Dart, Malik Willis and the top
  20, with both values.

## 5. Prior Looks

- **Today's in-season value's results are known,** including the 9 Nov group ratios: 5-or-fewer-games rows produced
  39% of value, and 2+ weeks out hurt 74% (`PREREG-ovs-available-ppg.md` §10).
- **No mixed value has been compared with any outcome.**
- **The baseline frame's accuracy is known** from the in-season study (`PREREG-ovs-in-season.md`).
- **Counts looked at before lock** (no outcomes compared): rows per games-so-far bucket, and the n = 0 rows' names,
  values and outcomes, to understand who they are.
- **Reproduction:** today's value on the test rows reads RMSE 48.4611, the same as re-running `ovs_qb_starts.py` on
  the same data folder. The 9 Nov results file reads 48.4610: a data refresh, 0.0003%.

## 6. Crash Tests, Before Lock

Run the in-season study's worlds with this design, re-picking K inside each run:

- **Noise:** outcomes shuffled within position and season. It may pass at most 1 of 20.
- **Planted:** outcomes built from the mix at K = 4, plus noise at the real miss size, as in the era study. K must be
  re-picked from the fit rows and the test must pass at least 80% of 200.
- **If the planted world fails,** it goes to Steve before any real run.

**Results (12 Nov, `study/out/ovs_small_samples_crash.json`):** noise passed 0 of 20. Planted passed 200 of 200 (median
lift 3.0%; K re-picked as 4 in 174 runs, 8 in 26). PASS.

## 7. Limits

- **Week 9 only:** the mix would apply at every week, but only week 9 is tested.
- **One trust number for every position.**
- **Before 2009 there are no injury reports,** so 'available' games in some fit seasons lean on roster status alone.
- **Heavy weight on the preseason value early on:** at week 1 the value is mostly preseason. That's the intent.

## 8. Not Licensed Here

- **The DELTA Score, the live site and buy/sell calls.**
- **The crowd board,** which is separate.

## 9. Amendments

None yet.
