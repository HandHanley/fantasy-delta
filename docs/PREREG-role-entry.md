# PRE-REGISTRATION — Will This Rookie Ever Earn A Role? Honest Odds, And What Sharpens Them

**Written:** 29 September 2026. No outcome has been looked at: the only runs were `--count` (players and
data coverage), spot checks of ages and speed scores, a self-check of the odds fit on made-up data, and
crash tests with every outcome replaced by random hits (they prove the code runs — nothing more).
**Status:** locks on commit. **Script:** `scripts/role-entry-study.py`.

---

## 1. Why

Every rookie study so far graded only players who reached the field. The dynasty question is earlier:
**will this rookie ever become a fantasy starter at all?** DELTA's market-independent research already
found the rookie *distribution* matters more than its average ("a Day 3 receiver averages 3.3 PPG and
medians 1.7, but one in ten peaks at 9.2"). Suggested by the outside review of 29 Sep; the owner wants
rookie signals DELTA can stand behind — honest odds are one.

---

## 2. The Outcome

**Every drafted QB/RB/WR/TE of 2015–2023 (712 players), busts included.** A **hit** = at least one
**starter-level season within his first three**: top 12 QB, top 24 RB, top 24 WR or top 12 TE by points
per game among players with 8+ games that season (the breakout studies' definition; half PPR + TE
premium). A player who never plays is a miss. 2023 is the last class with three seasons done.

---

## 3. Part A — The Odds

- **Model:** for each position, the log-odds of a hit fall in a straight line with the log of the pick
  (`a + b × ln(pick)`) — smooth, so pick 107 and pick 250 differ, and no tiny buckets (Rookie Baseline v2's
  lesson). Each class is predicted from the other eight.
- **Honest enough to show?** The ten-bin average calibration error (predicted vs actual hit rate) must be no
  worse than a **perfectly honest model would show by chance** on this many players — outcomes simulated
  2,000 times from the model's own odds; the real error must sit at or below the 95th percentile.
  **Why not a fixed limit:** a 5-point limit failed perfectly honest noise in the crash test, because with
  ~70 players a bin chance alone moves a bin 4–5 points. On random data the check still (correctly) flags
  a curve fitted to noise as dishonest in most runs.
- **Reported:** Brier score vs a position-only base rate; hit rates by position; the fitted curves and odds
  at picks 5, 20, 45, 80, 120, 180, 240; undrafted rookies' hit rates (994, many never played).

---

## 4. Part B — Does Anything Sharpen The Odds Beyond Draft Slot?

Each adds **one** pooled term to Part A's model, compared within position:

| Test | Term | Players | Why |
|---|---|---|---|
| **B1** | **Age** at the start of the rookie season (7 Sep — the engine's rule; nflverse birth dates) | all 712 | Younger draftees are widely believed to hit more often at the same draft slot |
| **B2** | **Athleticism**: speed score (weight × 200 ÷ forty⁴) | RB/WR/TE who ran a forty (450 of 611) — the baseline is refitted on the same players | Speed for size, beyond what teams already paid for |
| reported only | college **dDOM** | classes 2021–2023 | Too few players to test (college data starts in 2020) |

**Pass mark for each — all four:** (1) Brier score at least **2% better**; (2) paired shuffle test per player
**p < 0.025** — stricter than usual because **two** terms are tested (it keeps two tries from doubling the
chance of a lucky pass); 2,000 shuffles, seed 20260929; (3) better in **at least 6 of 9** classes; (4) no
position with 30+ players more than 1% worse.

**Missing forty times are not random** — players skip when injured or when their stock is safe (Puka
Nacua ran none). B2 therefore speaks only for players who ran.

**Stated in advance so it can be wrong:** Part A **honest enough to show**; **B1 age confirmed** (the most
established finding of the three); **B2 not confirmed** — draft slot already prices athleticism.

---

## 5. What It Could Lead To

- **Part A honest:** a design for **rookie odds on player cards** — e.g. *"Chance of a starter season by
  year 3: 13%"* — using the curve fitted on all nine classes. Display only: no projection, Score or call
  changes. Build agreed with the owner first.
- **A confirmed add-on:** the displayed odds include that term.
- **Nothing here changes the engine's numbers.**

---

## Pre-Lock Checks (29 September 2026)

| Check | Result |
|---|---|
| Inputs for known players | Barkley pick 2, age 21.6, 4.40 / 233 lb → speed 124.3 · Jefferson 104.9 · Pitts 126.1 · Bijan 108.7 · Nacua no forty |
| Odds-fit self-check (made-up data, true −1.0 / 0.8) | Recovered −0.96 / 0.78 |
| Coverage | 712 drafted (WR 290, RB 189, TE 132, QB 101); birth dates 712 of 712; speed score 450 of 611 RB/WR/TE; undrafted rookies 994 |
| Crash tests, random hits | Add-ons never confirmed; honest-odds check flags curves fitted to noise in 2 of 3 runs |
| `--run` refuses while this file is uncommitted | Refused |

---

## Amendments

*(none)*
