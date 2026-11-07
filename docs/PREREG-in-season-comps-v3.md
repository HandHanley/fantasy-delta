# PRE-REGISTRATION (DRAFT, NOT LOCKED) — In-Season Comps, Lean Correction By Position

**Drafted 7 Nov 2026** at Steve's request ("Let's try option 1"), after v2 (`docs/PREREG-in-season-comps-v2.md`)
failed its crash tests. **NOT LOCKED: crash tests failed, so it was not run. No real outcome was looked at.**

## The Only Change From v2

The correction factor k is measured **separately for each position** for players in year 2 and up (QB, RB, WR, TE).
This season's rookies stay pooled across positions, because there are too few per position. Everything else is v2
word for word: rows, matching, weights, binomial thinning, r = min(1, k), weeks, test seasons 2013–2020, bars, and
crash tests at 40 runs per world with a bar of 32. Script: `study/comps_in_season_v3.py`.

## Crash Result (7 Nov) — `study/out/comps_in_season_v3_crash.json`

| World | Corrected Odds Passed Honesty | Bar | v2 (One k For Everyone) |
|---|---|---|---|
| Honest (no lean) | 30 of 40 | 32 | 34 of 40 |
| Lean (16% high everywhere) | 30 of 40 | 32 | 30 of 40 |
| Uncorrected, lean world (must be caught) | caught 20 of 20 | 16 | 20 of 20 |

Splitting by position made the honest world **worse**. Each position's k is measured on fewer players, so it wobbles,
and a k that wobbles below 1 by chance pulls honest odds down. The correction costs honesty about as much as it
fixes. Per the process, not locked and not run.

## Where This Leaves It

Two drafts of an after-the-fact correction (v2, v3) both fail on made-up data where the right answer is known. The
in-season version stays off the card. The planned veteran fix ("Fix 3") runs on the 2023 players in early 2027. If
it removes the lean at its source, in-season matching can be tested again then, without a correction layer.
