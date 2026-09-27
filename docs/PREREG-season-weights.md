# PRE-REGISTRATION — How Much Should Each Past Season Count?

**Written:** 26 September 2026. No outcome has been looked at: the only runs were `--count`
(eligibility, no errors) and a crash test with every outcome replaced by random numbers (proves the
code runs — nothing more).
**Status:** locks on commit. Changes after the first run go in Amendments, with a reason.
**Script:** `scripts/weights-study.py` — `--count`, then `--run`, which refuses unless this file is
committed and unedited. Games, scoring and player IDs come from `scripts/blend-study.py`, unchanged.

---

## 1. Why

The projection starts from a weighted average of a player's last three seasons. The engine and
`scripts/backtest.js` describe that differently, and `backtest.js` says its rule *is* the engine's:

| | Engine (`calcProj`, "RULE 1") | `backtest.js` |
|---|---|---|
| Weights | 3 / 2 / 1 (50% / 33% / 17%) | 60% / 30% / 10% |
| Short seasons | Only last season is cut back, in steps: full at 10+ games, half at 8–9, a quarter at 4–7, none under 4 | Every season scaled smoothly by games ÷ 8 |
| Older seasons | Full weight if he scored at all | Scaled by games |

**This study decides which rule the engine should use.** Whatever the result, `backtest.js`'s
description gets corrected so the two stop disagreeing silently.

---

## 2. The Question

Before a season starts, which rule's starting number better predicts a player's points per game for
that season?

- **Graded:** QB/RB/WR/TE with 8+ played games across the three prior seasons and 6+ in the season
  being predicted (the `backtest.js` and ledger rules). Games by the live DNP rule; scoring
  `backtest.js`'s formula (half PPR + TE premium); players tracked by nflverse ID.
- **Data:** nflverse weekly stats and snap counts, 2015–2025. **Training** 2018–2022; **held out**
  2023–2025, graded once.
- **Only the weighting is on trial.** The later adjustments to the starting number — the 25% "sat out
  last season" discount, the QB starter adjustment, age, team and every multiplier — are untouched.

---

## 3. The Contenders

Twelve combinations, fixed now: weights **3/2/1, 6/3/1, 5/3/2, 4/2/1, 7/2/1, 1/1/1**, each with
one of two short-season rules — **steps** (today's rule, on last season only) or **smooth** (every
season scaled by games ÷ 8).

- **E, today's engine = 3/2/1 steps.** Copied exactly: it reproduces the live engine's own starting
  number for all 315 veterans whose number isn't later adjusted (26 Sep), and matches that verified
  copy on 20,000 random inputs.
- **The candidate** is whichever of the other 11 has the lowest average error across the five
  training seasons. Held-out numbers cannot change the choice.

---

## 4. The Pass Mark — All Four, Or The Engine Keeps Its Rule

1. **Size:** the candidate's typical miss (RMSE) at least **2% lower** than E's on 2023–2025.
2. **Not a fluke:** paired shuffle test, p < 0.05, 2,000 shuffles, seed 20260926, one-sided: E's and
   the candidate's errors are swapped **per player** (a player can appear in up to three held-out
   seasons). This compares two real predictions on the same players, so it does not share the
   market-form study's flaw (a predictor replaced by noise at a fitted weight).
3. **Every held-out season:** better in 2023, 2024 and 2025 each.
4. **No position harmed:** no position with 30+ held-out player-seasons more than 1% worse.

**Stated in advance so it can be wrong:** the most likely result is **"not shown"**. The weightings
are not far apart, and a 2% improvement on a whole-season forecast is a lot to find from reweighting
the same three numbers. If the short-season rule matters, "smooth" should edge "steps".

**Reported only:** average miss (MAE) for E and the candidate, and every combination's held-out error.

---

## 5. What Happens After

- **Pass:** `calcProj` "RULE 1" changes to the candidate; before-and-after table; Engine Audit 32/32;
  DELTA Scores unchanged. The in-season blend's K values were fit against a 60/30/10 smooth prior and
  were flat between 3 and 6, so they are not re-fit.
- **Not shown:** the engine keeps 3/2/1 steps, and `backtest.js`'s comment is corrected to say the
  harness uses a simplified 60/30/10 rule that is not the engine's. Its behaviour is not changed, so
  past backtest numbers stay reproducible.

---

## Pre-Lock Checks (26 September 2026)

| Check | Result |
|---|---|
| Today's rule vs the live engine's own starting number (`26e`) | 315 of 315 veterans identical; the other 24 are all later adjustments — 21 exactly the 25% "sat out 2025" discount, 3 the QB starter adjustment |
| The script's copy of today's rule vs that verified copy | 0 mismatches on 20,000 random inputs |
| `--run` refuses while this file is uncommitted | Refused |
| Full `--run` path, outcomes replaced by random numbers | Runs end to end — crash test only |

**Graded player-seasons** (printed by `--count` before any error was computed): 2018 315 · 2019 317 ·
2020 339 · 2021 362 · 2022 346 · **2023 344 · 2024 364 · 2025 346**. Training 1,679; held out 1,054
from 518 players (WR 435, TE 273, RB 236, QB 110).

---

## Amendments

*(none)*
