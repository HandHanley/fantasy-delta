# PRE-REGISTRATION — Are Running Quarterbacks A Safer Bet Year To Year?

**Written:** 4 October 2026. No outcome has been looked at: the only runs were `--count` (pairs and groups built
from season-Y data only; the script prints nothing from the following season) and crash tests in which every
following season was replaced by synthetic numbers (they prove the code runs and the tests are fair — nothing more).
**Status:** locks on commit. Changes after the first run go in Amendments, with a reason.
**Script:** `scripts/qb-rushing-study.py` — `--count`, `--crash`, then `--run`, which refuses unless this file is
committed and unedited.
**What kind of study:** content for the newsletter. **It changes nothing in the engine** and needs no ship gate.
Pre-registered so it can be published as found.

---

## 1. The Question

Fantasy analysis widely holds that a quarterback's rushing is "sticky" — that a running QB is a safer bet than a
pocket passer. **Take two QBs who scored the same last season at the same age, one with a big share from rushing
and one without: does the runner keep more of his points the next season, and is his next season easier to
predict?**

---

## 2. The Data

- **nflverse weekly player stats, 1999–2025,** regular season. Loader `scripts/qb-missedtime-study.py` `load()`,
  imported unchanged.
- **A start** is the house definition: his team's most pass attempts that game, **10 or more** —
  `scripts/qb-perstart-study.py` `starts_table()`, imported unchanged. Everything is **points per start**.
- **DELTA's QB scoring, split in two:** passing = yards × 0.04 + TDs × 4 − INTs × 2; rushing = yards × 0.1 + TDs × 6.
- **A pair:** a QB with **8+ starts in season Y and 8+ starts in Y+1**, Y = 1999–2024, age known (nflverse birth
  date, on 1 September). **574 pairs from 126 QBs** (1999–2011: 274 · 2012–2024: 300).
- **Groups, by rushing share of his season-Y points, in thirds within each season:**
  **Runners** (top third, median 21% from rushing) · **Middle** · **Pocket** (bottom third, median 3%).
  e.g. 2024 Runners: Jalen Hurts, Josh Allen, Bryce Young, Daniel Jones, Lamar Jackson, Drake Maye ·
  2024 Pocket: Jordan Love, Aaron Rodgers, Tua Tagovailoa, Matthew Stafford, Jared Goff, Kirk Cousins.

---

## 3. The Tests

**The comparison line:** next season's points per start, predicted from this season's points per start and age —
a straight line **fitted on the Middle third only**, then applied to Runners and Pocket alike.

| Test | Plain English | Measure |
|---|---|---|
| **Q2 — Points Kept** | Does a runner keep more points than a pocket QB who scored the same at the same age? | Runners' average gap to the line minus Pocket's |
| **Q3 — Steadiness** | Is a runner's next season easier to predict? | Runners' average size of miss to the line minus Pocket's (negative = runners steadier) |

**A test is SHOWN only if all three hold:**
1. **Size:** at least **1.0 point per start** (Q2) or **0.5** (Q3).
2. **Not a fluke:** its **99%** range excludes zero — 4,000 resamples of **QBs** (a QB appears in many pairs),
   refitting the line each time, seed 20261004. 99% because there are two tests.
3. **Holds in both halves:** 1999–2011 and 2012–2024 point the same way.

**Reported only — Q1, "Stickiness":** the year-to-year correlation of rushing points per start minus that of
passing. **Why it is not a test:** in the crash test, giving passing and rushing the *same* ±25% year-to-year wobble
still read "rushing stickier" (+0.27 in both runs). QBs differ far more in rushing (3% to 21% of their points) than in
passing, and a wide spread ranks well from one year to the next even when the wobble is identical. So a high rushing
correlation is expected by arithmetic, and **the article must not present it as proof that rushing is more
reliable.**

**Also reported only:** rank correlations; each half on its own; Q2 without age in the line; the five biggest
Runner drops and gains.

---

## 4. Out Of Scope, On Purpose

**Whether running QBs miss more games is not studied.** DELTA does not measure or label injury-proneness. Every
pair requires 8+ starts in both seasons, so this is a study of **how production repeats when he plays** — and the
article must say so in those words, because it means the study cannot claim runners are "safer" overall.

---

## 5. Honest Limits

- **Q2 finds differences of about 3 points per start or more.** A planted +3 was SHOWN (+2.8); a planted +2 read
  +1.3 with a range up to +2.5 — not shown. A real gap of 1–2 points per start would likely read "not shown".
- **Survivors only** (§4): QBs who lost the job or were hurt are not in the pairs.
- **Thirds are relative within a season;** a 1999 "Runner" ran less than a 2024 one.
- **4-point passing TDs.** In 6-point leagues passing carries more weight and the groups would differ.

---

## 6. Prior Work — Full Disclosure

- **QB points per start (`PREREG-qb-perstart.md`, 2 Oct):** graded how QB points per start repeat, on 277
  thin-history QB-seasons 2002–2025. It never split passing from rushing.
- **QB TD% regression (Aug, `study/td_pct_study.py`):** passing TD rate regresses; below the bar.
- **Seen before locking:** pair counts, group sizes, season-Y rushing shares and names, and crash-test output on
  synthetic next seasons.

---

## 7. Stated In Advance, So It Can Be Wrong

- **Q2:** Runners keep a little more — positive — but **not shown** (under 3 points per start).
- **Q3:** not shown.
- **Q1 (reported):** rushing correlation well above passing — expected by arithmetic (§3).

---

## 8. What It Could Lead To

A newsletter article — working title **"Are Running Quarterbacks A Safer Bet?"** — reporting both tests as found and
explaining why the popular "stickiness" number overstates the case. **No engine change.**

---

## Pre-Lock Checks (4 October 2026)

| Check | Result |
|---|---|
| QB-seasons with 8+ starts, 1999–2025 | 850 |
| Pairs | 574 from 126 QBs; halves 274 / 300; Runners 200 · Middle 190 · Pocket 184 |
| **Flaw 1 caught** | Line fitted on all pairs let a Runners-only effect leak into the age term (Runners skew young). Now fitted on the Middle only |
| **Flaw 2 caught** | Q1 read "rushing stickier" (+0.27) when both had identical wobble. Q1 demoted to reported only, with the reason (§3) |
| Design change before lock | Age enters the line straight, not curved — fewer things fitted on the Middle's 190 pairs |
| Null runs (3 with no link to last season, 2 with realistic carry-over) | Q2 and Q3: 0 of 10 SHOWN |
| Planted effects | Runners +3 a start → Q2 SHOWN (+2.8) · +2 → not shown (+1.3, power limit, §5) · Runners steadier → Q3 SHOWN (−1.47) |
| `--run` refuses while this file is uncommitted | Refused |

---

## Amendments

*(none)*

---

## Result (4 October 2026) — Not Shown, Not Shown: The "Rushing Is Sticky" Edge Is Mostly Arithmetic

Run once, `python3 scripts/qb-rushing-study.py --run`, against this file as committed in `0316a28`
(sha256 prefix `4862539f4b22a2ce`, printed by the run). Nothing above this section was changed after the run.
Full output: `study/out/report_qb_rushing.txt`. 574 pairs from 126 QBs, as counted before lock.

| Test | Runners | Pocket | Difference (99% Range) | Both Halves | Verdict |
|---|---|---|---|---|---|
| **Q2 — Points kept** (gap to the line, points per start) | +0.83 | +0.08 | **+0.746** (−0.286 to +1.803) | +0.330 / +1.282 | **Not shown** |
| **Q3 — Steadiness** (size of miss, points per start) | 2.42 | 2.33 | **+0.089** (−0.465 to +0.686) | +0.035 / +0.217 | **Not shown** |
| Q1 — "Stickiness", reported only | rushing 0.812 | passing 0.554 | +0.258 (+0.117 to +0.401) | +0.198 / +0.358 | Reported only (§3) |

**Predictions (§7): three of three.** Q2 positive but not shown; Q3 not shown; rushing correlation well above passing.

**What it says, plainly:**

- **Rushing does repeat more than passing** (0.81 vs 0.55) — but the crash test showed most of that gap appears even
  when both are equally reliable, because QBs differ far more in how much they run. **It is not evidence that a
  runner is the safer bet.**
- **Given two QBs who scored the same at the same age, the runner kept about three-quarters of a point per start
  more** the next season — roughly 12–13 points over a 17-game season. Both halves point that way, but the range
  includes zero, so it is **not shown**. The study can confirm only gaps of about 3 points per start (§5).
- **Runners are not more predictable.** Their next season missed the line by 2.42 points per start against 2.33 for
  pocket QBs — if anything slightly less steady.
- **Pay for the points, not for the legs.** Nothing here supports a premium for rushing on its own.

**Reported only:** the newer half leans further toward runners (kept +1.17 vs −0.12) than the older half (+0.55 vs
+0.22) — a hint, not a finding. Dropping age from the line changes nothing (+0.84 vs +0.08). Rank correlations
agree (rushing 0.772, passing 0.537). **"Runner" means a big share of points from rushing, which can also mean weak
passing:** the biggest Runner drops include JaMarcus Russell 2008 and Mark Sanchez 2011, alongside the gains of
Kyler Murray 2019, Cam Newton 2014 and Josh Allen 2019.

**Limits, restated:** production when he plays only — availability is out of scope by design (§4); survivors with
8+ starts in both seasons; 4-point passing TDs.

**What it leads to:** the newsletter article (§8). No engine change.
