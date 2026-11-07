# PRE-REGISTRATION — Historical Comps During The Season

**Drafted:** 7 November 2026, before any in-season result existed. **Window A chosen by Steve, 7 Nov** ("Agree with A,
your pick"). **LOCKED** by the commit that adds this file with `study/comps_in_season.py` and its crash-test output
`study/out/comps_in_season_crash.json`. Run once after that.

## Summary

The Historical Comps card matches every player as he looked when **last season ended**. Nine weeks into 2026,
that ignores half a season. This tests one fix: match players as they look **this week**, against past players **at the
same week of their season**, and check that the odds stay honest.

## The Window (Steve's Choice, A)

At week W of season Y the odds are about **the three seasons after this one** (Y+1 to Y+3). None of it has
happened yet. Once in-season matching starts, the card's chip changes from 2026–2028 to 2027–2029.

## What Changes (And What Doesn't)

**One new kind of snapshot:** a player as of the end of week W of season Y. Every rule not listed here stays as
locked in `docs/PREREG-comparables-value.md`, `PREREG-draft-drop.md` (Version A) and `PREREG-honest-odds.md` (Fix 2).

| Feature | In-Season Version | Baseline (This Season Ignored) |
|---|---|---|
| Points per game | 3/2/1 with **this season so far as the newest season** (if he has a game in it), then the two seasons before | 3/2/1 over his last three full seasons |
| Games | **Games so far this season** | Games last season |
| Age | 7 Sep of season Y (same in both) | Same |
| Year in the league | Counting season Y (same in both) | Same |
| Draft slot | Version A: dropped from year 2 | Same |
| This season's rookies | **Veterans in year 1**: production so far, games, age, draft slot (draft weight `1.5 × 24 / (G + 24)`, G = career games) | Matched as at the draft: draft slot and age |

- **Who is a row:** anyone with a game in season Y through week W, or a game last season (Y − 1). Rookies who haven't
  played by week W are left out of both versions; the card keeps their season-end row.
- **Who can match:** rows at the **same week W** from seasons ≤ Y − 4, so their three following seasons are complete.
  Pool rows start in 2002 (the first season whose three prior seasons are in the weekly file).
- **Nothing is fitted.** Same 30 matches, same weights, same Fix 2 recency weighting (half-life 8 seasons).

## Baseline

The same rows at the same week, with this season's play ignored (right-hand column above). It differs from the
in-season version **only in points per game and games**, and for this season's rookies. Age and year in the league are
the same in both: they are time, not play. So the comparison answers one thing: does this season's play help?

## Tests

- **Weeks:** W = 5, 9, 13.
- **Primary test seasons:** Y = 2021 and 2022 (outcomes 2022–2025).
- **Reported only:** Y = 2009–2012 (honesty and Brier), and every season 2005–2022 (Brier only).

## Bar (Set Before Any Result)

For each week W, on 2021–22:

1. **Honest:** the A6 rule, the same rule the other odds passed.
   - Overall calibration error inside the 95th percentile of an honest forecaster's.
   - Each position inside the 99.375th percentile.
   - Measured for both the chance of at least one starter season and the expected number of starter seasons.
2. **Not worse:** the in-season Brier score (chance of at least one starter season) no more than **1% worse** than the
   baseline's. Whether it is clearly *better* is reported with a one-sided permutation p-value, signs flipped by player
   (10,000 flips). It is not required.

**Decision:**

- If **W = 5, 9 and 13 all pass**, the card uses in-season matching from week 5 through the end of the regular
  season, and today's season-end matching before week 5.
- If any week fails, the card stays as it is today all year, and we say so plainly.
- No partial adoption. That would be choosing after seeing results.

## Crash Tests (Run Before Lock, Week 9)

- **Noise world:** outcomes shuffled within position and season. "Better than baseline" (lower Brier and p < 0.05)
  may come up in at most 5% of 100 runs.
- **Planted world:** truth driven by in-season points per game, at the strength season-end production shows on
  pool-only seasons (≤ 2016, never a test row). Fitted on baseline features only, so no in-season outcome relation is
  looked at. The test must catch it in at least 16 of 20 runs.
- **Leak check:** asserted on every row. No match's window reaches past the test season; no player is matched to
  himself.

## Disclosure

- The season-end versions of these odds have been tested on 2021–22 and 2009–12, and those results are known: Fix 2
  honest, narrowly; rookies read 2–5 points low. No in-season result has been looked at.
- The motive is freshness of the card (Steve, 7 Nov), not any result.
- This is a display number. It never feeds the DELTA Score, a value or a call. The DELTA model's ≥2% RMSE rule does
  not apply; the honesty rule does.

## What Goes Live If It Passes

- `study/build_historical_comps.py` gains `--week W`, built from the weekly file. The data file is rebuilt each week
  of the season.
- The card's heading reads **"Matched On · As Of Week W"**, and the chip moves to the next three seasons.

## Amendments (All Before Lock, Before Any Result)

- **A1. Points check.** The draft required weekly points to match the season file to 0.01 for every player-season.
  - Run on 14,713 player-seasons: 4% differ by more than 0.01, almost all in 1999–2005 (11% of those seasons), and only
    1.4% by more than 5 points. Games differ more, because the weekly file has rows for weeks with no touch.
  - Now: features for **both** versions come from the weekly file (so they share one source), and a game is a week
    with a pass, carry, target or catch (that matches the season file's games 96.8% of the time).
  - The run stops only if more than 5% of player-seasons differ by over 5 points, or by over one game.
  - Outcomes still come from the season file, exactly as in the other studies.
- **A2. Rows and baseline spelled out**, as in the table above. This covers who is a row, rookies who haven't
  played, and age and year in the league being the same in both versions.
- **A3. Noise crash test: 100 runs instead of 20.** The first 20-run noise test had 2 false alarms (10%). A
  100-run check then had 4 (4%), with the p-values spread evenly as they should be under noise. Twenty runs can't
  measure a 5% rate; 2 of 20 happens by chance about a quarter of the time. Thresholds unchanged.
