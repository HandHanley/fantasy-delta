# PRE-REGISTRATION — QB Points Per Start, And The Few-Starts Modifier

**Written:** 2 October 2026. **Status:** DRAFT — locks when committed together with the script, byte-identical
to the copy reviewed. **Script:** `scripts/qb-perstart-study.py`.

---

## 1. The Question

**Owner's decision (2 Oct 2026), not on trial here:** a quarterback's projection means his **points per game when
he starts**. Starts only; no backup cut (×0.55) and no missed-time cut on a QB projection. The backup cut mixed
"how good is he" with "how much will he play" — a QB2 halved describes neither.

**On trial:** the few-starts modifier. A thin record is noisy (Malik Willis's seven starts before Miami ranged from
1.4 to 31.5 points), so a projection should lean on it less the fewer starts there are. Today's starter lift blends
toward the **established-starter median**. But established starters kept their jobs by being good; a backup who
gets a job is, on average, a lower-level player. Willis's last four Green Bay starts averaged 18.4; his whole
record 13.2; his first three Miami starts 13.1.

- **Baseline** — today's lift, translated to starts: `(n × own + 6 × sb) ÷ (n + 6)`.
- **Candidate** — `(n × own + K × a·sb) ÷ (n + K)`, with **K** (how fast trust builds) and **a** (the anchor as a
  share of the median) fitted.

`n` = his starts across the three prior seasons; `own` = his points per start over them (3/2/1 season weights,
each season weighted also by its starts); `sb` = the median points per start of QBs with 14+ starts the season
before (set each season — it drifts from about 13 in the 2000s to about 18 now). No prior starts: the anchor alone.

If the data says the anchor should equal the median and trust builds at today's pace, the candidate **is** the
baseline and cannot pass.

---

## 2. The Data

nflverse weekly player stats, regular season, 1999–2025, loaded by `scripts/qb-missedtime-study.py` `load()`
unchanged (any recorded production; the same rule every season).

- **A start:** the player with his team's most pass attempts in that game, 10 or more — found by attempts, never the
  position label (nflverse labels by latest position).
- **Points:** `scripts/blend-study.py` `bt_pts()`, DELTA's half-PPR basis.
- **Graded:** every QB-season **2002–2025** with **4+ starts**, by a player with any NFL appearance in the three prior
  seasons. True rookies are excluded — the engine's rookie path does not change.
- **Groups:** **thin** = 16 or fewer starts across the three prior seasons; **established** = more.

**Counts** (printed by `--count`; no outcomes): **893 QB-seasons** — thin **277** (147 in 2002–2013, 130 in
2014–2025), established 616; 34 with no prior starts.

---

## 3. The Test — Every Season Graded, Never On Its Own Fit

**Leave one season out:** each season is forecast with K and a fitted on the **other 23 seasons** only — a grid of
K 1–30 and a 0.70–1.10 (step 0.01), minimising the typical miss over every graded QB-season in those seasons.

**Pass mark — all four:**
1. **Size:** across the 277 thin-history QB-seasons, the typical miss (RMSE, points per start) is **at least 2%
   lower** than the baseline's.
2. **Not a fluke:** paired shuffle test — each QB-season's two real forecasts swapped at random, 2,000 shuffles,
   seed 20261003, one-sided, **p < 0.05**.
3. **Both halves:** the thin group is better in 2002–2013 **and** 2014–2025.
4. **Established QBs not harmed:** the 616 established QB-seasons no more than 1% worse.

**Reported only, never gated:** K and a for each left-out season; the size fitted on all 24 seasons; average miss
(MAE); per-start trust with **no** modifier; and, for context on the definition change, **today's engine number
graded per start** — approximated as today's per-appearance starting number × missed-time cut, because the QB lift's
named-starter list and the backup flags cannot be rebuilt for past seasons.

---

## 4. The Odds — Measured Before Locking

The crash test replaced every outcome with synthetic numbers **before anything was computed** (real outcomes are
discarded in memory in `--count` and `--crash`). Noise averages exactly 1; 0.20 is near the realistic level for a
season's points per start, 0.30 pessimistic. 200 simulations each.

| If The Truth Is… | Passes (Realistic / Pessimistic Noise) |
|---|---|
| Today's anchor and pace are right | **0% / 0%** |
| The anchor should be 8% lower | 56% / 13% |
| The anchor should be 15% lower | 99% / 83% |
| Trust should build slower (K 15) | 60% / 22% |

The median fit recovered the true K and a in every scenario. **A first design** fitted on 2002–2014 and graded only
2015–2025 (121 thin QB-seasons): the same 0% on a right baseline but 34% / 11% on an 8% gap. Changed to leave one
season out before any outcome was seen.

**Read plainly:** it never moves the anchor when today's is right, catches a large gap almost always, and a small
one about half the time.

---

## 5. What Ships

**Either way, as a separate build reviewed with before-and-after numbers** (the definition is the owner's call):
QB projections become points per start. The pipeline adds starts and points per start for 2023–2025; the engine's
QB projection uses the formula above; the in-season blend counts starts only; the ×0.55 backup cut leaves the QB
projection and moves to model value only (owner, 2 Oct); the DELTA Score holds; the Scorecard grades QBs per start;
rookies are unchanged. The named-starter list and the 2 Oct QB exception are superseded by the modifier.

- **If it passes:** K and a fitted on all 24 seasons.
- **If it fails:** the baseline — K = 6, anchor = the median. **Not re-run** with other gates, groups or grids.

**Untested extensions, flagged:** counting only starts in the in-season blend; the modifier for a QB who becomes the
starter mid-season.

---

## 6. Every Earlier Look At This Data

- **The hypothesis came from a seen result.** Today's QB study (`docs/PREREG-qb-missedtime.md`) reported a best
  fit of ×0.92 after the lift on 103 thin-history Week-1 starters, 2002–2025 — per-appearance outcomes, overlapping
  QB-seasons. This test is **not independent** of that observation.
- **The lift's K = 6** was fitted on 2000–2014 Week-1 starters and checked on 2015–2024.
- **Malik Willis's career** (2022–2026, starts and relief split, including his first three 2026 starts) was looked
  at today to frame the question. One player; nothing is tuned to him.
- **2 October (this session):** `--count`; crash tests on synthetic outcomes; the engine's 2025 starter level (17.70)
  read for illustration; the design changed to leave one season out after the first crash test.

---

## Pre-Lock Checks (2 October 2026)

| Check | Result |
|---|---|
| Loader and scoring | Imported unchanged from the locked study scripts |
| Fast fit equals brute force over the grid | Identical on a test set |
| `--run` refuses while this file is uncommitted | Refused |
| Full path, including the reporting step, on synthetic outcomes | Runs end to end; §4 |

---

## Amendments

*(none)*

## Result

*(not run)*
