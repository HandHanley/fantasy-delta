# PRE-REGISTRATION — New Value: No One Match Carries A Player

**Drafted:** 13 November 2026, before any capped value has been compared with any outcome. **Status: LOCKED; amended A1 before any real run (§3A).** Locked by
committing this document with `study/ovs_one_match.py`. The crash test runs next; the real run only if it passes.
Steve, 13 Nov: "Yeah let's do a study for option 1."

---

## Plain-English Summary (For Steve)

**The problem.** A player's New Value is the average of what his 30 most similar past players went on to score. For a
long shot, most of those 30 scored nothing, and one or two stars carry the whole value. Athan Kaliakmanis (pick 223)
has 27 zeros among his 30; Brock Purdy and Dak Prescott make up 96% of his value. The same thing lifts Matthew
Caldwell, Drew Allar, Barion Brown (Tyreek Hill, 58%) and others.

**The fix being tested.** Before averaging, no match counts for more than the player's third-best match. For
Kaliakmanis, Purdy and Prescott each count as Matt Cassel's total. A star whose matches are all stars barely moves,
because his third-best match is a star too.

**Why the third-best.** It's the smallest number that still lets a player with two strong matches keep some of
them, and it was picked before any result. Second, fourth and fifth are reported beside it, deciding nothing.

**The test.** The usual bar: on 2013–2022 players at week 9, the capped values must miss by at least 2% less (typical
miss), with the permutation check. A crash test runs first to see whether the 2% bar can even see a change like this.

## 1. Frame

- `ovs_small_samples.setup`: week 9, test rows 2013–2022 (6,808), outcome FV3 (next three seasons above the starter
  line). Its assertion that today's in-season value reproduces (RMSE 48.4611) must pass.
- **Today = the live build:** in-season value, with first-year players who have no game (QBs: no real game) or are
  under 150 offensive snaps this season on their incoming-rookie value (`PREREG-ovs-rookie-snaps.md`). Reproduced
  before drafting: first-year RMSE 55.95 (as that study), all test rows 48.334.
- **Capped:** the same matches and the same weights. Each match's outcome is replaced by min(outcome, the
  third-highest outcome among that player's matches), then averaged. Applied to both the in-season value and the
  incoming-rookie value, so every player is treated alike. Only past players' outcomes are used, as today.

## 2. Decision

- **Rows:** all test rows, every position.
- **Passes** if capped RMSE is at least **2% lower** than today's, with paired permutation p < 0.05 (10,000 shuffles,
  each player's snapshots swapped together; `comps_value_study.perm_test`).
- **Passes →** the weekly build caps at the third-best match (Steve's OK first). **Fails →** no change.

## 3. Crash Tests, Before Any Real Run

- **Noise:** outcomes shuffled within position and season, both values rebuilt from the shuffled outcomes. May pass
  at most 1 of 20.
- **Planted:** a world where the capped value is right: truth = capped value + real misses (outcome − capped value)
  shuffled within position, floored at zero. Must pass at least 80% of 200.
- **If the planted test fails,** this goes to Steve before any real run, with options. Nothing is run against real
  outcomes until he decides.

**Results (13 Nov, `study/out/ovs_one_match_crash.json`):** noise passed 0 of 20 (OK). Planted passed **0 of 200,
FAIL**, median lift −0.6%.

**Why, and a second planted test.** The planted world above is broken by construction: flooring at zero and shuffling
misses across players lifts long shots' planted outcomes back toward today's value, so "the cap is right" isn't what
it plants. A cleaner planted world, run before any real run (`study/out/ovs_one_match_crash_draw*.json`): each player
"becomes" one of his own 30 matches, drawn by match weight, with that match's outcome capped (cap-is-right world) or
not (today-is-right world). It uses no test player's own outcome.

| World | All Rows: Passes | All Rows: Median Lift | Rows The Cap Moves 20%+: Passes | Median Lift |
|---|---|---|---|---|
| Cap is right | 0 of 200 | +0.5% | **200 of 200** | +5.9% |
| Today is right | 0 of 50 | −0.4% | 0 of 50 | −1.4% |

On all rows the 2% bar can't see this change even when it's exactly right (the same wall as Contract Security and the
rookie calibration): typical miss is driven by stars' big misses, and long shots' values are small numbers. On the
rows it moves (3,339 of 6,808 test rows, chosen from values alone, no outcomes), the test sees it every time and
never falsely. **Taken to Steve before any real run.**

## 3A. Amendment A1 (13 Nov, After The Crash Tests, Before Any Real Run)

Steve approved deciding where the cap acts ("Yep that makes sense"), after the plain version: the all-rows grade
can't hear a change this small even when it's exactly right; graded on the players it changes, it hears it every time
and never falsely. **Replaces section 2's decision:**

- **Decided on:** test rows whose value the cap lowers by **20% or more**, chosen from today's and the capped values
  alone (no outcome read). 3,339 of 6,808.
- **Passes** if capped RMSE on those rows is at least **2% lower**, permutation p < 0.05 (10,000 shuffles), **and**
  RMSE on all test rows is at most **0.5% worse**.
- **Noise check first:** outcomes shuffled within position and season, values and the 20% rows rebuilt from them. May
  pass at most 1 of 20 (`--mode crash_a1`). Planted: the match-draw test above, 200 of 200.
- Section 2's all-rows result is reported beside it, deciding nothing. Passes → the weekly build caps at the
  third-best match. Fails → no change.

## 4. Reported, Deciding Nothing

- Caps at the second, fourth and fifth match.
- By position.
- Rank correlation (Spearman) with the outcome, today and capped.
- Produced ÷ value by fifths of today's value, today and capped.
- Late-round rookies (picks 101+) on their draft value: produced ÷ value and RMSE, today and capped.
- If it passes: what moves in this week's build.

## 5. Prior Looks (Recorded Before Drafting)

On 13 Nov, on this frame with today's values, outcomes visible (`/tmp/diag/late_rookies.py`):

- Late-round rookies (picks 101+) under 150 snaps at week 9: 545 rows, average value 9.1, produced 3.7 (0.41×), 6%
  became starters. Veterans in the same value range: 2,206 rows, 0.51×, 7%.
- By draft range, rookies under 150 snaps produced ÷ value: picks 1–32 0.34, 33–64 0.88, 65–100 0.65, 101–160 0.47,
  161+/undrafted 0.33. Rookies with 150+ snaps: 1.23, 1.07, 0.97, 0.80, 0.53.
- 2026 build, week 9 (no outcomes): matches that scored zero and the top matches' share, for Kaliakmanis, Strand,
  Barion Brown, Virgil, Brenen Thompson, Klein, Jordan James, Skyler Bell (summary above).
- **No capped value has been compared with any outcome.** The rule (cap at the third-best) was chosen from the 2026
  examples, not from outcomes.

## 6. Limits

- One cap for every player and position.
- It lowers values only. If the bottom of the board is generous to everyone (the 0.51× above), this fixes some of
  that too, and the test can't separate the two.
- It doesn't touch which 30 players are matched, or how much recent seasons count.

## 7. Not Licensed Here

The DELTA Score, the live site's main rankings, buy/sell calls.
