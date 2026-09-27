# PRE-REGISTRATION — How Big Should The Missed-Time Penalties Be?

**Written:** 27 September 2026. No outcome has been looked at: the only runs were `--count`
(eligibility, no errors) and crash tests with every outcome replaced by random numbers (they prove the
code runs — nothing more).
**Status:** locks on commit. Changes after the first run go in Amendments, with a reason.
**Script:** `scripts/missed-time-study.py` — `--count`, then `--run`, which refuses unless this file is
committed and unedited. The starting number is imported from `scripts/weights-study.py` (the engine's
own rule, verified 315/315); games, scoring and player IDs from `scripts/blend-study.py`.

---

## 1. What Is Decided, And What Is On Trial

**Decided (owner, handoff §2, 26 Sep 2026):** missed time counts. A player who missed real time last
season has shown less ability to stay healthy and has less game experience, and backups who didn't
play are meant to be hit too.

**On trial: only the size of each penalty.** A fitted size is capped at ×1.00 — it may shrink towards
"no penalty", never become a bonus. If the data says a penalty should be about zero, that goes back to
the owner as a finding; it does not remove the lever.

---

## 2. The Penalties Being Sized

Grouped by games played in the season before the one being predicted:

| Group | Situation | Today's Penalty | Combined |
|---|---|---|---|
| **S1** | Sat out that season, played the one before | 25% cut, then −12% | ×0.66 |
| **S2** | Sat out that season and the one before it | 25% cut, then −18% | ×0.615 |
| **P1** | Played 1–3 games | −8% | ×0.92 |
| **P2** | Played 4–7 games | −4% | ×0.96 |

All four come on top of the starting number already giving that short season little or no weight.
**Simplification, disclosed:** in the live engine the −12/−18/−8/−4 sit inside `calcProj`'s cap on
combined adjustments (−25%, QBs −15%), so a few players receive a little less than the table shows.
This study applies the penalties as plain multipliers.

**S2 is too small to size alone** (6 cases in eight seasons). It keeps today's extra penalty relative
to S1: its size is always S1's × (0.615 ÷ 0.66).

---

## 3. The Question And Data

For each group: when the player comes back and plays **6+ games**, what multiplier on the starting
number best predicts his points per game that season?

- **Graded:** QB/RB/WR/TE in a group above, with 8+ played games across the three prior seasons and 6+
  in the season being predicted (the weights study's rules, imported unchanged).
- **Data:** nflverse weekly stats and snap counts, 2015–2025; seasons predicted 2018–2025. Games by the
  live DNP rule; `backtest.js` scoring (half PPR + TE premium); players tracked by nflverse ID.
- **Fitting:** for each group, the one multiplier that minimises the squared miss (`Σ base × actual ÷
  Σ base²`), capped at 1.00.

---

## 4. Why This Study Is Evaluated Differently

The earlier studies fitted on 2018–2022 and graded once on 2023–2025. **Here that leaves only 125 test
cases** (S1 19, S2 2, P1 37, P2 67) — too few for a fair verdict either way. So:

**Every season takes a turn as the test season.** Each of the eight seasons 2018–2025 is predicted with
sizes fitted on the other seven, never on itself. All **360 cases** (302 players) are then graded out
of sample. The sizes that would ship are fitted on all eight.

---

## 5. The Pass Mark — All Four, Or Today's Sizes Stay

1. **Size:** the fitted sizes' typical miss (RMSE) at least **2% lower** than today's, across the 360.
2. **Not a fluke:** paired shuffle test, p < 0.05, 2,000 shuffles, seed 20260927, one-sided; today's and
   the fitted errors are swapped **per player** (a player can appear in several seasons).
3. **Most seasons:** better in **at least 6 of the 8** seasons. About 45 cases a season makes "all 8"
   close to a coin toss even for a real improvement.
4. **No position harmed:** no position with 30+ cases more than 1% worse.

**Stated in advance so it can be wrong:** I have no firm expectation. The direction should hold (the
owner's rule is not on trial). With 360 cases, only a clearly wrong current size will clear 2%.

**Reported only:** each group's own improvement, the uncapped fitted sizes, and the sizes each season
was predicted with.

---

## 6. What Happens After

- **Pass:** the four penalties change to the sizes fitted on all eight seasons (S2 keeping its relative
  gap). The exact build — how the combined multiplier replaces the 25% cut and the −12%/−18%, and how
  the −8%/−4% change — is agreed with the owner before it's written. Before-and-after table; Engine
  Audit 32/32.
- **Not shown:** today's sizes stay. The finding (the fitted sizes and how close they came) is recorded.
- **Not in this study:** the missed-time cuts inside **model value** (−4% for 1–8 games, the blank-season
  cuts) cannot be graded against points; the DELTA Score's full-season zero is part of a different claim.

---

## Pre-Lock Checks (27 September 2026)

| Check | Result |
|---|---|
| Starting number | Imported from `scripts/weights-study.py` — the engine's rule, verified 315/315 against the live engine |
| Today's sizes | Read from the live engine `2026-09-27b`: ×0.75 stale discount (`calcProj`), `d_decay` −0.12/−0.18/−0.08/−0.04 ("RULE 5") |
| `--run` refuses while this file is uncommitted | Refused |
| Full `--run` path, outcomes replaced by random numbers | Runs end to end — crash test only |

**Graded player-seasons** (printed by `--count`, before any error was computed):

| Season | P1 (1–3 games) | P2 (4–7) | S1 (sat out one) | S2 (sat out two) |
|---|---|---|---|---|
| 2018 | 11 | 15 | 12 | 1 |
| 2019 | 8 | 30 | 7 | 0 |
| 2020 | 15 | 19 | 10 | 3 |
| 2021 | 21 | 28 | 9 | 0 |
| 2022 | 12 | 26 | 8 | 0 |
| 2023 | 11 | 25 | 6 | 0 |
| 2024 | 17 | 18 | 7 | 2 |
| 2025 | 9 | 24 | 6 | 0 |

Total 360 from 302 players (WR 141, RB 85, TE 78, QB 56).

---

## Amendments

*(none)*
