# PRE-REGISTRATION — Honest Odds, Follow-Up: League Size For Veterans Only

**Drafted:** 2 November 2026, before any result exists. **Status: LOCKED** by the commit that adds this file with `study/honest_odds_v3.py`. Approved to run by Steve (2 Nov, "run option 1
now and just see if it tells us anything"). Locked by committing it with `study/honest_odds_v3.py` before the real run.

## Plain-English Summary

Earlier today (`docs/PREREG-honest-odds.md`), **Fix 2** (recent comparables count more) was the only version with honest
three-year odds on fresh 2021–22 players. Its veterans still leaned about 3 points high, and Fix 1 (league size) fixed
veterans but sank rookies. That suggested **Fix 3: Fix 2 for everyone, plus league size for veterans only.**

Because that idea came from today's results, it has to be tested on players whose three-year odds have **never** been
graded: the **2009–2012 offseasons.** The same run also gives **Fix 2 a second independent check.**

## 1. Test Set

Every veteran and incoming rookie at the end of seasons `t` = 2009, 2010, 2011 and 2012, built exactly as today (roster
positions, three-year horizon, pool ≤ `t − 3`). Their outcomes were used before only as other players' comparables; no
prediction **for** them has ever been graded. Limitation, stated up front: their comparables come from 2001 onward, so
they are only 3–11 seasons older than the players, and the effects these fixes target are smaller here than today.

## 2. Versions

- **Fix 2** — as locked in `docs/PREREG-honest-odds.md` (`356f183`).
- **Fix 3** — Fix 2's weights for everyone; for **veterans only**, each comparable's result also scaled by
  `N(s, pos) / N(t, pos)`, capped at 1 (Fix 1's rule). Rookies are identical to Fix 2. Nothing fitted.

## 3. Questions

- **Q-A, Fix 3 vs Fix 2 (decides whether Fix 3 replaces Fix 2):** Fix 3 replaces Fix 2 only if (1) Fix 3 is honest under
  the same A6 rule, **and** (2) Fix 3's starter-season odds miss less (lower Brier score), with a paired permutation test
  (10,000 shuffles, all of a player's rows swapped together) giving p < 0.05.
- **Q-B, Fix 2 re-check (reported; decides nothing on its own):** is Fix 2 honest on 2009–2012 too, under the A6 rule?

## 4. Size Check First

- **World 1, Fix 3 is right:** outcomes drawn from Fix 3's own odds. Q-A should switch to Fix 3 in **≥ 80% of 200 runs.**
- **World 2, Fix 2 is right:** outcomes drawn from Fix 2's own odds. Q-A must **not** switch in at least 95% of runs, and
  Fix 2 should be judged honest in ≥ 80%.
- **World 3, the lean we saw:** outcomes from Fix 2's odds with veterans at 0.86× (today's 17.1/19.8). Fix 2's re-check
  should call it dishonest in ≥ 80% of runs.

**If World 1 is under 80%, Q-A is not run** (too weak to tell the two apart) and that is the answer. **If World 3 is under
80%, Q-B is reported as "can't detect today's lean on these players"** rather than as a pass. Whatever runs, runs once.

## 5. Amendments

### Pre-lock (2 Nov 2026)

- **A1. Sample, counted (no outcomes).** 2,320 rows from 980 players: 2,003 veterans, 317 incoming rookies. Average stated
  veteran chance: Fix 2 23.7%, Fix 3 21.9% (the two differ by under 2 points on these players, as §1 warned).
- **A2. Size check (200 runs each; the size check's permutation tests used 2,000 shuffles for speed).**

  | World | Result | Bar | Verdict |
  |---|---|---|---|
  | 1: Fix 3 is right | Q-A switched to Fix 3 in **41%** | ≥ 80% | **Too weak: Q-A is not run** |
  | 2: Fix 2 is right | Q-A falsely switched in 0%; Fix 2 judged honest in 81.5% | ≤ 5%; ≥ 80% | OK |
  | 3: veterans lean like today (0.86×) | Fix 2 called dishonest in **98.5%** | ≥ 80% | **Q-B runs** |

  So the only real result is Q-B: is Fix 2 honest on 2009–2012? `study/honest_odds_v3.py` was changed before lock to
  compute Q-B only.
