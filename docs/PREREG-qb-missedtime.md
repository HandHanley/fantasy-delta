# PRE-REGISTRATION — QB Starter Lift × Missed-Time Cut

**Written:** 2 October 2026. **Status:** DRAFT — locks when committed together with the script, byte-identical
to the copy reviewed. **Script:** `scripts/qb-missedtime-study.py`.

---

## 1. The Question

For a Week-1 starting quarterback who played **under 8 games last season**, the engine does two things in a row
(`delta-engine.js` 29a, `calcProj`):

1. **The starter lift:** pulls his starting number toward a typical starter's level — weight on his own number
   `g ÷ (g + 6)`, the rest on the median of quarterbacks with 14+ games last season.
2. **The missed-time cut:** then multiplies by ×0.797 (4–7 games last season), ×0.690 (1–3), or ×0.721 / ×0.672
   (skipped the season).

The missed-time sizes were measured on the plain starting number, never after the lift (`PREREG-missed-time.md`:
"Not tested by the study"). **Is the cut double-counting what the lift already handles?**

**Live = lift × cut. Candidate = lift only.** The engine stacks them today, so the change on trial is removing the
cut for these quarterbacks.

---

## 2. What It Would Change Today

Run through the live engine (`29a`) on 2 October data, with the cut switched off only where the lift fires:
**3 of 409 players change, all quarterbacks; nobody else moves.**

| QB | Games Last Season | Projection Today | Without The Cut | Change |
|---|---|---|---|---|
| Jayden Daniels | 7 | 14.92 | 17.35 | +16.3% |
| Kyler Murray | 5 | 9.59 | 11.60 | +21.0% |
| Malik Willis | 4 | 11.05 | 12.44 | +12.6% |

The in-season blend already carries about four weeks of 2026 games, so each moves less than the full cut.

---

## 3. The Data

nflverse weekly player stats, regular season, 1999–2025 (GitHub releases).

- **Graded seasons: 2002–2025**, so every graded season has all three prior seasons on file.
- **Played game:** any recorded production, **the same rule in every season**. Snap counts do not exist before
  2013 (the 2012 file has zero rows), so the live rule (1+ snap or any production) cannot be applied across the
  whole span. Count-only check on 2014–2025: **4 of 51** quarterbacks land differently under the live rule —
  Derek Anderson 2014 and Jameis Winston 2021 would move from the 1–3 group to the 4–7 group; Marcus Mariota
  2022 and Joe Flacco 2025 would reach 8 games and fall outside the lift.
- **Week-1 starter:** the player with the most pass attempts (10+) in his team's first game — **found by attempts,
  not position label**, because nflverse labels a player by his latest position (Terrelle Pryor 2013 is listed
  as a receiver). Fixed before any outcome was seen; it changed no counts.
- **Eligible — exactly when the lift fires in the engine:** under 8 games last season, and a usable history
  (4+ games last season, or any production two or three seasons back). True rookies never reach the lift.
- **Graded:** 4+ played games in the season itself.
- **Typical starter level:** each season, the median points per game of quarterbacks with 14+ games the
  season before — as `qbStarterBaseline()` does.

**Counts** (printed by `--count`; no outcomes): **103 quarterbacks** — 4–7 games last season 62, 1–3 games
32, skipped season 9. Halves: 52 (2002–2013) and 51 (2014–2025). No season has more than 8; 2013 has none
(its only veteran candidate, Pryor, had 3 games and no earlier history, so the lift does not fire).

---

## 4. The Forecasts

Imported **unchanged**: the engine's starting number (`scripts/weights-study.py` `base()`, 3/2/1 "steps",
verified 315/315 against the live engine), the missed-time sizes (`scripts/startprofile-study.py`
`mt_mult()`, identical to `missedTimeMult()`), and backtest scoring (`scripts/blend-study.py` `bt_pts()`,
half PPR). The lift is written out as in `calcProj` (K = 6).

**Outcome:** points per game over his played games that season.

**Absolute, not calibrated:** the question is which forecast the engine should show, so both are graded as they
stand. Forecasts that run a little high in general would favour keeping a cut — this works **against** the
candidate, never for it.

---

## 5. Pass Mark — All Four

1. **Size:** removing the cut lowers the typical miss (RMSE) by **at least 2%**, pooled over all 103.
2. **Not a fluke:** paired shuffle test — each quarterback's two real forecasts swapped at random, 2,000
   shuffles, seed 20261002, one-sided, **p < 0.05**.
3. **Both halves:** better in 2002–2013 **and** in 2014–2025.
4. **No cut group harmed:** no group with 25+ quarterbacks (in practice: 4–7 games, 1–3 games) more than 1%
   worse.

**Reported only, never gated:** whether the **cut is confirmed** (keeping it beats removing it by 2%+, reverse
p < 0.05); the best-fit multiplier on top of the lift, by group; average miss (MAE). A different cut size is
**not** on trial — it would need its own pre-registration on data this run has not touched.

---

## 6. The Odds — Measured Before Locking

The crash test replaced every outcome with synthetic numbers **before anything was computed** (real outcomes
are discarded in memory in `--count` and `--crash`). Forecasts were set 3% high, as in life; noise averages
exactly 1, at 0.25 (the lift's recorded typical miss on these quarterbacks, about 2.6 on ~15) and 0.35
(pessimistic). 200 simulations each.

| If The Truth Is… | Removing The Cut Passes (Realistic / Pessimistic Noise) |
|---|---|
| The cut is exactly right | **0% / 0%** |
| The cut is three-quarters right | 0% / 0% |
| The cut is half right | 0% / 0.5% |
| The cut is pure double-counting | **97.5% / 77.5%** |

**Read plainly:** the test only removes the cut when it is mostly or wholly double-counting, and then it almost
always says so. A cut that is partly right stays. (A first crash run used noise that averaged slightly above 1,
which quietly favoured removal; corrected before locking.)

---

## 7. What Ships If It Passes

In `calcProj`, the missed-time cut is **not applied when the QB starter lift fired** (named Week-1 starter,
under 8 games last season, usable history, starter level available). One condition on one line; the cut stays
for every other player. Before-and-after table on the live engine (§2 is the preview); Engine Audit 32/32.

**If it fails:** nothing changes. **Do not re-run** with different gates, groups, seasons or a different
played-game rule.

---

## 8. Every Earlier Look At This Data

- **The lift itself** was measured on Week-1 starters 2000–2024 (engine comment: MAE 4.22 → 2.64, n = 97;
  K fitted on 2000–2014, checked on 2015–2024). Those seasons' outcomes have been seen **for the lift**. Whether
  the cut belongs on top of it has never been measured. The lift's K is the same in both forecasts here.
- **The missed-time sizes** were fitted on 2018–2022 using the plain starting number (360 cases from 302
  players, 56 of the cases quarterbacks, 8+ games across three prior seasons). Some of these 103 may sit in that set.
- **1–2 October (this session):** a rough count of Week-1 starters with thin seasons (team, attempts and game
  counts only); `--count`; the 2013 diagnosis; the played-game-rule comparison (game counts only); the
  before-and-after preview in §2 (live 2026 projections, no historical outcome); crash tests on synthetic
  outcomes. A power simulation on made-up numbers framed the question as removing the cut.

---

## Pre-Lock Checks (2 October 2026)

| Check | Result |
|---|---|
| Starting number, cut sizes, scoring | Imported unchanged from the locked study scripts |
| Engine `29a`, cut applied after the lift and outside the later caps | Read in `calcProj` |
| Today's effect | 3 of 409 players change (§2) |
| `--run` refuses while this file is uncommitted | Refused |
| Full path on synthetic outcomes | Runs end to end; §6 |

---

## Amendments

*(none)*

## Result

*(not run)*
