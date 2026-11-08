# PRE-REGISTRATION — Own Value Scale: Expected Points From Usage

**Drafted:** 8 November 2026. **Status: NOT LOCKED, NOT RUN — the crash test failed (§9).** Steve: "Let's do the expected points plan and run it."
Locks by committing this document with `study/ovs_xfp.py` and its crash results, before the one real run; runs only
if the crash tests pass.

Starts from the Own Value Scale as adopted on 8 Nov: era-adjusted matching (`docs/PREREG-ovs-era.md`), this season's
games counted (`docs/PREREG-ovs-in-season.md`), three seasons ahead.

---

## Plain-English Summary (For Steve)

**The gap.** The matching sees only points. Two players can score the same points, one on a heavy, secure workload and
one on touchdown luck. The market prices the difference; the value can't. It's the common thread in Gibbs, Bowers and
the young QBs.

**The ingredient.** Expected points: what a player's carries, targets and where they happened on the field would
usually score, from every play since 2006. Free (ffverse/ffopportunity, built from nflverse play-by-play).

**The change.** Matching weighs production half on actual points, half on expected points. Nothing else changes.

**The test.** Does it predict the next three seasons at least 2% better, at week 9 (the in-season value) and at the end
of the regular season (the offseason value)?

## 1. Data

- **Expected points:** `ep_weekly_YYYY.csv`, 2006–2026, from `github.com/ffverse/ffopportunity` releases
  (`latest-data`). The package is GPL-3 (an open licence that allows commercial use; DELTA would show only its own
  derived values). Built by applying an xgboost model to nflverse play-by-play.
- **Checked before any outcome (8 Nov):** same player IDs as nflverse; `total_fantasy_points` matches nflverse's
  full-PPR points within 0.5 on 98.1% of player-weeks, so it is full PPR. Converted to DELTA's scoring as
  `expected − 0.5 × expected catches (+ 0.5 × expected catches for TEs)`. Playoff weeks dropped by keeping only
  regular-season weeks in which the player had a game in the weekly file. Coverage: 100% of those games.
- **Disclosed limit:** the model was trained on 2006–2020 plays, which overlaps the test seasons. That is general
  scoring patterns (what a target at the 5 is usually worth), not any player's future; a small, stated leak.

## 2. The Change, And Only The Change

- **Expected production** = 3/2/1 over this season so far, last season and the one before, of `(expected points per
  game) ÷ (that season's starter level at his position)`, the same games, weights and starter levels as actual
  production.
- **Matching weights:** production 3.0 → **1.5 actual + 1.5 expected**. Age, draft slot (Version A), career year,
  games, 30 matches, Fix 2 weights: unchanged. Rookie (draft-day) matching unchanged.
- **Both versions use the same rows and pool:** seasons from 2008 (a row needs seasons Y − 2 to Y), pool `≤ Y − 4` at
  the same week, outcome FV3 (Y + 1 to Y + 3). Test seasons 2015–2022. Week 9: 5,470 rows, 1,577 players; week 18:
  5,815 rows.

## 3. The Questions

- **Week 9 (the in-season value)** and **week 18 (end of the regular season, standing in for the offseason value)**.
- Each: RMSE lift ≥ 2%, paired permutation p < 0.025 (two tests), 10,000 shuffles, a player's rows together; trades no
  more than 1.0 point worse.
- **Decision:** week 9 passes → the in-season value (weeks 5+) uses expected points. Week 18 passes → the offseason
  value uses it. Each needs Steve's OK to go further.

## 4. Reported, Deciding Nothing

By position; today's values at 2026 week 9 for Gibbs, Bowers, McBride, Dart, Mayfield and the top 25.

## 5. Prior Looks

- The adopted Own Value Scale's results on 2013–2022 are known (in-season: 4.2–8.8% better than ignoring the season).
- No expected-points feature has been compared with any outcome. One spot check of the feature itself: Derrick Henry
  2020, actual 1.24× a starter, expected 1.03×.

## 6. Crash Tests, Before Lock

At week 9, both methods' real predictions: noise world (outcomes shuffled within position and season) passes in at
most 1 of 20; planted world w = 0.75 passes in ≥ 80% of 200; w = 0.6 reported. Leak checks asserted (pool `≤ Y − 4`,
from 2008, finished windows, no self-match).

## 7. Limits

- Pool from 2008 only, so the early test seasons have few past seasons to match against (2015: 2008–2011).
- Expected points describe usage, not talent; a player who always beats his usage is partly penalised for it.
- Week 18 approximates the offseason snapshot (weekly file, pool `≤ Y − 4`).

## 8. Not Licensed Here

The DELTA Score, the site's model value, buy/sell calls. Nothing on the site changes.

## 9. Amendments

**Crash result (8 Nov, week 9, `study/out/ovs_xfp_crash.json`): FAILED, so not locked and not run.**

| World | Runs | Passed | Typical Gain (Bar 2%) |
|---|---|---|---|
| Noise | 20 | 0 | — |
| Planted, w = 0.75 | 200 | **0** | 0.7% |
| Planted, w = 0.6 | 50 | 0 | 0.3% |

**Why.** Actual and expected production move together (correlation 0.94 for veterans), so the two versions share 75%
of their matches and their predictions correlate 0.98. Even if the expected-points version were exactly right, it
would beat the current one by under 1% overall: the bar can't be reached with this change. No real outcome was
compared with any expected-points prediction.

**Display look (no outcomes), 2026 week 9, both versions on the same 2008+ pool:** Gibbs unchanged (10th), Bijan 9th →
11th, Bowers 36th → 52nd, McBride 19th → 16th, Nacua 7th → 2nd, Dart 117th → 158th. Expected points would not have
moved the running backs or tight ends up.
