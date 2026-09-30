# PRE-REGISTRATION — Rookie Baseline v2: A Smooth Draft Curve, And A Baseline For Undrafted Rookies

**Written:** 29 September 2026. No forecast error has been computed: the only runs were `--count`, a
check of whether the engine's rookie table can be rebuilt (it cannot — §2), a self-check of the median-line
fit on an exact line, and crash tests with every rookie outcome replaced by random numbers.
**Status:** locks on commit. **Script:** `scripts/rookie-baseline-study.py`.

**Disclosure:** rookie seasons 2015–2025 have been used before — to build the engine's table (Aug), in
the rookie blend study (Part 2), and in the college study (rookie PPG). **Whether a smooth curve beats
the buckets, and what undrafted rookies should start at, has not been looked at.**

---

## 1. Why

Suggested by an outside review of DELTA's rookie research (29 Sep): every "does X help beyond draft slot?"
test uses the rookie baseline as its control, and it feeds the in-season rookie blend (Part 2, 23.3%).
Two weaknesses: (1) **five buckets** — pick 107 and pick 250 get the same number; (2) **undrafted rookies
get no baseline** — the engine falls back to a literal **8.0**, then applies the "sat out two seasons"
multiplier (×0.672 → **5.38**), which was never meant for rookies. Ten live players sit on that path
today (e.g. J'Mari Taylor, Robert Henry, Michael Trigg, Noah Thomas).

---

## 2. What "Today" Means Here

The engine's `ROOKIE_PPG` constants were fitted on **all** of 2015–2025 — every class this study tests —
and the script that built them is not in the repo. Rebuilding them with the documented recipe gives **725**
rookie seasons (the engine comment cites 718) and matches only **3 of 20** cells. So the literal constants
would enjoy a home advantage and cannot be reproduced. **The comparison is between methods**, each refitted
on the other ten classes:

- **Today's method:** median rookie PPG by position × five tiers (1–10, 11–32, 33–64, 65–105, 106+), rows
  forced non-increasing.
- The literal constants' error is **reported only**, marked in-sample.

---

## 3. Part A — Drafted Rookies

- **Candidate:** a **median curve** per position, `PPG = a + b × ln(pick)`, fitted by least absolute
  deviations with `b ≤ 0`, floored at zero.
- **Why a median curve, and why average miss:** fantasy points are right-skewed, so on RMSE any *average*
  beats any *median*, even on noise — the first crash test "shipped" a least-squares curve on random data
  for exactly that reason. Fitting medians on both sides leaves **smoothness** as the only difference, and
  the **average miss (MAE)** — the ledger's headline measure, and what a median targets — is the primary
  measure.
- **What the crash test still shows, and why that is legitimate:** on random data the median curve still
  tends to beat the buckets, because some buckets are tiny (a handful of top-10 QBs or TEs a year) and the
  non-increasing rule drags noisy tiers down. Pooling every pick at a position estimates better from the
  same data. Every class is predicted by a fit that never saw it, so that is a real out-of-sample edge — but
  a pass should be read as **"the curve estimates better"**, not **"exact pick is magic"**.
- **Reported only:** buckets built on averages vs medians (the separate "average or median?" question).

## 4. Part B — Undrafted Rookies

- **Who:** no draft round, first NFL season in 2015–2025, and played a game that season (nflverse
  `rookie_season`; e.g. Austin Ekeler 2017).
- **Today:** the engine's fallback core, 8.0 × 0.672 = **5.376** (later engine adjustments cannot be rebuilt
  for past seasons).
- **Candidate:** the **median** rookie PPG of past undrafted rookies at his position.
- On noise this also passes, as it should: 5.38 has no data behind it, so any data-based centre beats it
  wherever real undrafted rookies score differently. That is the question.

---

## 5. The Pass Mark — Each Part Separately, All Five

Each class 2015–2025 predicted once, from the other ten:
1. **Size:** average miss at least **2% lower**.
2. **Not a fluke:** paired shuffle test per player on average miss, p < 0.05, 2,000 shuffles, seed 20260929.
3. **Typical miss (RMSE) not worse.**
4. **Most classes:** better in **at least 8 of 11**.
5. **No position harmed:** none with 30+ players more than 1% worse (Part B: undrafted QBs, 12, are
   exempt by size).

**Stated in advance so it can be wrong:** Part A **passes, modestly**; Part B **passes clearly** — real
undrafted rookies who play score far below 5.38.

---

## 6. What Ships If A Part Passes

- **A:** `rookieBaseline()` uses the median curve (a, b per position, fitted on all eleven classes) instead
  of the tier table.
- **B:** undrafted rookies get the position median instead of the 8.0 fallback and its misapplied discount.
- **Both change rookies' projections and their DELTA Scores** (a rookie's Score reads his forward projection)
  — before-and-after table, Engine Audit 32/32, and the build agreed with the owner first. The in-season
  blend's K = 3 is not refitted (it was flat between 3 and 6); undrafted rookies stay **out** of the blend
  (K = 0) — adding them would need its own test.

---

## Pre-Lock Checks (29 September 2026)

| Check | Result |
|---|---|
| Rebuild the engine's `ROOKIE_PPG` from its recipe | 725 seasons, not 718; 3 of 20 cells match → compare methods, not constants (§2) |
| Median-line fit on an exact line (a = 10, b = −1.5) | 10.0000, −1.5000 |
| First crash test (least-squares curve) | "Shipped" on noise — right-skew artefact → median curve + average miss |
| Second crash tests, 3 random seeds | Part A passes 2 of 3 (small-bucket noise — §3); Part B 3 of 3 (§4) |
| `--run` refuses while this file is uncommitted | Refused |

**Counts** (printed by `--count`): drafted rookie seasons **725** (2015 60 · 2016 60 · 2017 64 · 2018 61 ·
2019 66 · 2020 66 · 2021 68 · 2022 69 · 2023 69 · 2024 70 · 2025 72; WR 303, RB 208, TE 133, QB 81).
Undrafted rookie seasons **406** (WR 180, RB 117, TE 97, QB 12).

---

## Amendments

*(none)*

## Result (29 September 2026) — Part A NOT SHOWN · Part B PASSED

Run once, `python3 scripts/rookie-baseline-study.py --run`, against this file as committed in `e30e2bc`
(sha256 prefix `bb84e16de7a1a5c6`). Nothing above this section was changed after the run.

**Part A — smooth median curve vs today's buckets (725 drafted rookie seasons): not shown.** Average miss
2.729 → 2.659 (**+2.5%**), typical miss 3.700 → 3.541 — but **p = 0.059**, better in only **7 of 11**
classes (2017, 2019, 2023, 2025 worse), and **WR −1.5%**, QB −1.4% (RB +5.2%, TE +11.4%). Three gates
fail; the buckets stay. The stated expectation ("passes, modestly") was wrong by a narrow margin.
**Reported only:** bucket averages vs medians — medians win on average miss (2.730 vs 2.798), averages on
typical miss (3.563 vs 3.700), as expected for skewed data. The engine's literal constants, in-sample:
average miss 2.653, typical miss 3.493 (home advantage — §2).

**Part B — undrafted baseline vs the 8.0 fallback (406 undrafted rookie seasons): PASSED all gates.**
Average miss 4.169 → **1.595 (+61.7%)**, typical miss 4.480 → 2.718, **p = 0.0005**, better in **all 11**
classes (+48% to +78%); RB +38.0%, WR +69.3%, TE +82.1%; QB −27.1% on 12 players (exempt by size).
**Undrafted baseline, median rookie PPG on all eleven classes:** QB 4.74 · RB 1.70 · WR 0.76 · TE 0.28.
The stated expectation (passes clearly) was right.

**§6 applies to Part B:** undrafted rookies get the position median instead of the 8.0 fallback — build
agreed with the owner first. **Found while preparing the build:** the 8.0 path also catches two
*veterans* whose stats are missing through a name mismatch (Joshua/Josh Palmer, Zonovan/Bam Knight), so
the build must fix those names first and tell an undrafted rookie from a veteran with missing data.
