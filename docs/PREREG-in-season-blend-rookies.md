# PRE-REGISTRATION — In-Season Blend, Part 2: Rookies And Thin-History Players

**Written:** 26 September 2026. No outcome for this question has been looked at: the only runs
were `--count` (eligibility, no errors) and a crash test with every outcome replaced by random
numbers (a crash test only — see Part 1, Amendment 2).
**Status:** locks on commit. Changes after the first run go in Amendments, with a reason.
**Script:** `scripts/blend-study-rookies.py` — `--count`, then `--run`, which refuses unless this
file is committed and unedited. It imports all shared machinery from `scripts/blend-study.py`
(Part 1), so games, scoring and IDs cannot drift between the two studies.

---

## 1. What Is Already Decided, And Is NOT On Trial

Part 1 (`docs/PREREG-in-season-blend.md`) PASSED on 26 Sep 2026 and shipped in `DL_BUILD 2026-09-26b`:
blending this season's points per game into the preseason projection, `w = G ÷ (G + 4)`, cut the
typical miss on rest-of-season PPG by 16.4%. It only covered players with **8+ played games in the
three prior seasons**. Everyone else keeps today's projection: every rookie, and veterans with a
thin record.

**This study tests whether the same kind of blend helps those two groups, and at what K.** Each
group is gated on its own and ships on its own. If a group fails, nothing changes for it.

---

## 2. The Two Groups

**R — Rookies.** Drafted players in their draft season. The prior is DELTA's rookie baseline recipe
(`ROOKIE_PPG`): the median rookie-season PPG for his position × draft-capital tier (picks 1–10,
11–32, 33–64, 65–105, 106+), rows forced non-increasing as capital falls.

**T — Thin history.** Everyone else with **1–7** played games across the three prior seasons (a
second-year player who barely played as a rookie, a veteran back from a lost year). The prior is
Part 1's preseason formula without its 8-game floor (each season is already shrunk by games ÷ 8).

Undrafted rookies (no capital, so no prior) are in neither group and keep today's path.

---

## 3. Prior Work — Full Disclosure

- **Part 1's result** (K = 4, 16.4%) is known. K for these groups is chosen fresh from the grid below.
- **The shipped `ROOKIE_PPG` table was fit on 2015–2025**, which includes the three seasons graded
  here. Using it as the prior would leak the answer in. The script that built it is **not in the
  repo**, so it can't be re-run exactly. This study rebuilds the recipe from nflverse data
  (live game-counting rule, `backtest.js` scoring). Rebuilt on 2015–2025 it lands within about
  1.5 PPG of the shipped table (RB and WR closer; QB and TE lower). **The prior used here:**
  held-out seasons use a table fit on **2015–2022**; each training season uses a table fit on
  2015–2022 **minus that season**, so no player's own rookie year is ever in his prior.
- **Counts were seen before locking** (below). No errors, predictions or outcomes were computed.

---

## 4. The Question, Data, And Contenders

Everything not stated here is exactly Part 1: checkpoints after Weeks 3, 6, 9 and 12; outcome =
rest-of-season PPG; graded if ≥1 game by the checkpoint and ≥4 after; the live DNP rule for games;
players tracked by nflverse ID; nflverse weekly stats and snap counts 2015–2025; training
2018–2022, held out 2023–2025.

- **A — prior only.**
- **B — blend:** `w × (PPG so far) + (1 − w) × prior`, `w = G ÷ (G + K)`.

**K grid, wider than Part 1's because a rookie prior is weaker:** 2, 3, 4, 6, 8, 10, 12, 16, 20,
24, 32. Chosen per group by leave-one-season-out inside 2018–2022; the final K is the best over all
five training seasons.

No penalty contender: the Start Profile penalty needs 20+ games, which these players almost never
have.

---

## 5. The Pass Mark — Per Group, All Four Or It Does Not Ship

1. **Size:** B's typical miss (RMSE, mean of the four checkpoint RMSEs) at least **2% lower** than A's.
2. **Not a fluke:** paired shuffle test, p < 0.05, 2,000 shuffles, seed 20260926, one-sided,
   swapping A and B within player-seasons (Part 1 §6).
3. **Every held-out season:** B beats A in 2023, 2024 and 2025 each.
4. **No position harmed:** B no more than 1% worse than A at any position **with at least 30
   held-out player-seasons** in that group. Below 30 the per-position number is reported, not gated
   (rookie QBs: 18).

**Reported only, never gated (group R):** the same comparison using the shipped engine table as the
prior — it includes the graded seasons, so it is optimistic, but it shows whether the rebuild
matters.

**Stated in advance so it can be wrong:** R should pass comfortably — a draft-slot median knows
nothing about the player, so his own games should take over fast, and K should come out at or
below Part 1's 4. **T may fail for lack of data** (74 held-out player-seasons, about 25 per season),
and a fail there means "not shown", not "shown not to help".

---

## 6. What Ships If A Group Passes

- **R:** the rookie branch of `calcProj` (the early return) blends at the group's K:
  `w × this-season PPG + (1 − w) × rookie projection`. The rookie projection keeps its age and
  availability multipliers, as today. The season-ender zeroing still runs after it.
- **T:** the main path blends at the group's K for players with 1–7 prior games, in exactly Part 1's
  form. Players with 8+ keep K = 4.
- Engine Audit 32/32; DELTA Scores must not move; before-and-after table for the owner's eye-test.

---

## Pre-Lock Checks (26 September 2026)

| Check | Result |
|---|---|
| Shared machinery | Imported from Part 1's script, which was validated 305/305 against the engine's Start Profile and 327/332 against `backtest.js` |
| Rookie-table recipe rebuilt on 2015–2025 vs the shipped table | Within ~1.5 PPG; RB and WR closer; QB and TE lower. The original build script is not in the repo |
| `--run` refuses while this file is uncommitted | Refused |
| Full `--run` path, every outcome replaced by random numbers | Runs end to end — a crash test only |

**Held-out prior table (fit 2015–2022, 514 rookie seasons), PPG by capital tier 1–10 / 11–32 / 33–64 / 65–105 / 106+:**
QB 13.51 / 11.37 / 11.37 / 8.56 / 2.73 · RB 16.32 / 11.37 / 11.20 / 7.06 / 3.22 ·
WR 9.04 / 6.88 / 6.04 / 3.32 / 1.30 · TE 8.56 / 6.49 / 4.00 / 2.47 / 1.27

**Graded player-checkpoints** (printed by `--count` before any error was computed):

| Season | R Wk 3 | R Wk 6 | R Wk 9 | R Wk 12 | T Wk 3 | T Wk 6 | T Wk 9 | T Wk 12 |
|---|---|---|---|---|---|---|---|---|
| 2018 | 43 | 50 | 47 | 43 | 25 | 23 | 22 | 18 |
| 2019 | 39 | 39 | 38 | 36 | 19 | 21 | 20 | 18 |
| 2020 | 47 | 50 | 49 | 40 | 20 | 29 | 22 | 18 |
| 2021 | 45 | 46 | 46 | 39 | 18 | 22 | 26 | 23 |
| 2022 | 41 | 52 | 54 | 50 | 23 | 23 | 20 | 15 |
| **2023** | 53 | 57 | 58 | 50 | 20 | 22 | 22 | 20 |
| **2024** | 47 | 49 | 51 | 45 | 16 | 18 | 17 | 16 |
| **2025** | 59 | 56 | 56 | 50 | 17 | 21 | 22 | 17 |

Held out: **R** 631 rows, 183 player-seasons (WR 84, RB 46, TE 35, QB 18) · **T** 228 rows, 74
player-seasons (WR 30, RB 20, TE 14, QB 10).

---

## Amendments

*(none)*
