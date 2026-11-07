# PRE-REGISTRATION — In-Season Historical Comps, With A Correction For The Lean

**Drafted:** 7 November 2026, after `docs/PREREG-in-season-comps.md` (locked `d03efe3`, results `c44f08b`).
**Approved by Steve, 7 Nov** ("Yeah let's try option 2"). **NOT LOCKED: the crash tests failed (A3), so this was not run.** It would have locked by the commit adding
this file with `study/comps_in_season_v2.py` and `study/out/comps_in_season_v2_crash.json`.

## Why

The first in-season test found two things:

- **More accurate:** this season's play made the matches clearly more accurate from week 9 on.
- **Not honest:** the odds ran about 2.5 points high, and that failed the honesty rule.

The version ignoring this season ran high too, so the lean isn't caused by using this season. This test adds a
correction for the lean and judges honesty on seasons whose in-season odds have never been judged.

## What's The Same

Everything in `docs/PREREG-in-season-comps.md` (window A, rows, features, matching, Version A, 30 matches, Fix 2,
weeks 5 / 9 / 13), unchanged and run through the same locked code (`study/comps_in_season.py`).

## The Correction (The Only New Thing)

For a player at week W of season Y:

1. **Measure the lean on the past only.** Take every in-season row from seasons 2006 to Y − 4. Their three-year
   windows had finished by week W of season Y. Divide the starter seasons that actually happened by the starter
   seasons the odds expected. Call that **k**. It's measured separately for:
   - this season's rookies (year 1);
   - everyone else (year 2 and up).
2. **Apply it.** Each of his 30 matches counts its starter seasons as if each one only happened with chance
   **r = min(1, k)**. So:
   - the chance of at least one starter season becomes `1 − (1 − r)^count`, per match, averaged with the Fix 2
     weights;
   - the expected number becomes `r × count`.
3. **The correction can only pull the odds down.** If a group ran low (k > 1, as rookies have), it's left alone.

Nothing is fitted to the test seasons. For the live card in 2026, k comes from seasons 2006–2022.

## Tests

- **Weeks:** 5, 9, 13.
- **Judged on Y = 2013–2020.** In-season honesty has never been judged on these seasons.
- **Reported only:** 2021–22 and 2009–12 (judged in the first test), with the same correction.

## Bar (Set Before Any Result)

For each week, on 2013–2020:

1. **Honest (corrected odds):** the A6 rule, unchanged.
   - Overall at the 95th percentile.
   - Each position at the 99.375th.
   - Both the chance of at least one starter season and the expected number.
2. **Not worse:** the corrected Brier score no more than 1% worse than the baseline's (this season ignored,
   uncorrected). Whether it's clearly better is reported (one-sided permutation p, signs flipped by player).

**Decision:**

- **Weeks 5, 9 and 13 all pass:** the card uses corrected in-season matching from week 5 to the end of the regular
  season, and season-end matching before that.
- **Any week fails:** the card stays as it is today all year.
- No partial adoption.

## Crash Tests (Week 9, Synthetic Outcomes Only, Before Lock)

Outcomes are drawn oldest season first, each row from its own matches' already-drawn outcomes. Each starter
season is kept with chance `scale`.

- **Honest world (scale 1):** the corrected odds must pass the honesty rule in at least 32 of 40 runs.
- **Lean world (scale 0.84, the size of the lean seen):**
  - the corrected odds must pass in at least 32 of 40 runs;
  - the uncorrected odds must be caught (fail) in at least 16 of 20 runs.
- **Leak checks:** asserted. No k uses a season later than Y − 4, no match comes from a season later than Y − 4, and
  no player is matched to himself.

## Disclosure

- The first test's report included Brier scores pooled across 2005–2022. Those cover these seasons, so overall
  accuracy here is roughly known: in-season was 7–13% better. The honesty of in-season odds on 2013–2020 has not
  been looked at, and neither has any corrected odds' result anywhere.
- The size of the lean (about 2.5 points on 2021–22) comes from the first test. It sets only the lean-world crash
  test, not the correction, which measures k on past seasons by itself.
- Display number only. It never feeds the DELTA Score, a value or a call.

## Amendments (Before Lock, Before Any Result)

- **A1. How the correction thins.** The first draft thinned each match's "at least one starter season" flag by r
  directly (the existing Fix 1 code path). The lean-world crash test showed that over-corrects players with two or
  three starter seasons: in a world planted 16% high, it said 14.1% against 16.5% happened. Thinning each starter
  season (binomial) fixed it: it said 16.8% against 16.6% happened. That is the rule above.
- **A2. Honest-world crash test: 40 runs, not 20.** The first full crash run had the corrected odds passing 14 of 20
  in the honest world (the bar was 16). That rule fails a perfectly honest forecaster about 15% of the time on its own.
  A 40-run check put the corrected odds at 35 of 40 and an already-honest uncorrected forecaster at 34 of 40, the same
  rate. So the correction wasn't hurting; 20 runs were too few to tell. Both worlds now use 40 runs with the same 80%
  bar (32 of 40). The uncorrected-in-lean-world check stays at 16 of 20 (it was caught 20 of 20).
- **A3. Crash result, 7 Nov: FAILED, so no lock and no run.** At 40 runs per world:
  - honest world: 34 of 40 passes;
  - lean world: 30 of 40 passes (bar 32);
  - uncorrected odds in the lean world: caught 20 of 20.

  A 30-run diagnostic in the lean world had 22 passes (73%). On average the correction lands right: said minus
  happened was −0.03 points, give or take 0.5. But it fails the bin-by-bin check (overall chance of at least one
  starter season) more often than an honest forecaster does (about 75% passing against 85%). The correction fixes the
  average but not the shape well enough to trust it. Options for a v3: correct by position, or measure k on a longer
  run of seasons. No real outcome was looked at for any of this.
