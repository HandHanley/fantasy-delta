# PRE-REGISTRATION — Historical Comps: QB Production From Real Games Only

**Drafted and locked:** 10 November 2026, by the commit that adds this file with `study/hc_qb_honesty.py`, before its
one run.

Steve: "the 2023 data should not be in there. Those are mostly games where he came in as the backup to end a game … The
same checklist for a confirmed start we use for start profiles should also be applied in here." Then, on the
few-games problem (Malik Willis 9.5 → 26.6 PPG on 3 real games): "Yeah let's run it."

---

## Plain-English Summary (For Steve)

**The question.** Which version of the card's odds actually came true for past QBs?

**The versions:**

- **Today:** cameos counted.
- **Start rule:** a QB's season counts only his real games (a start, or 75%+ of snaps), with cameos out.
- **Start rule + 4-game minimum:** the same, and a season with fewer than 4 real games doesn't count at all.

**The bar.** The card's odds are "honest" when they miss by no more than an honest forecast would by luck. That is the
1 Nov honesty check, run here for QBs.

## 1. The Versions

Everything is the card's build (`study/build_historical_comps.py`): Version A matching, Fix 2 weights, the three-season
window, 30 comparables, pool ≤ t − 3.

| Version | QB Season Points And Games (Production And Games Features Only) |
|---|---|
| Today | As recorded, cameos included |
| Start rule | Real games only (`study/qb_games.py`) |
| Start rule + 4 minimum | Real games only, and a season with fewer than 4 real games is left out. A QB with no season left has production 0 |

Outcomes (starter seasons in the next three) and which rows exist are identical in all three. Non-QB rows are
unaffected.

## 2. The Check

- **Rows:** veteran QB snapshots t = 2013–2022, all with three finished seasons.
  - These seasons were graded under today's version on 1 Nov. Neither new version has been graded.
- **Groups:**
  - all QB rows;
  - **few real games:** 4 or fewer real games in season t, under the start rule.
- **Honest:** the 1 Nov rule for each group, at the 95th percentile of 2,000 honest-forecaster simulations, on both of
  its measures:
  - **P3:** chance of at least one starter season;
  - **E3:** expected starter seasons.
- **Also reported:** the card's own shares (no / one / two-or-more starter seasons) said vs happened, and the Brier score
  for P3.

## 3. Decision

- **Ship** the version whose odds are honest in **both** groups.
- **If more than one is honest:** the one with the lower Brier score on all QB rows.
- **If neither new version is honest:** the card stays as it is today, and this goes back to Steve.

## 4. Not Licensed Here

The DELTA Score, model value, the Own Value Scale. This is the Historical Comps card only.

## 5. Results (10 Nov 2026, Run Once)

`study/out/hc_qb_honesty_results.json`. 754 veteran QB rows, 368 of them with 4 or fewer real games in season t.

**Decision under §3: no new version is honest in both groups, so the card stays as it is and this goes back to Steve.**
**Today's card is not honest for QBs either.**

| Check (error vs honest-luck limit) | Today | Start Rule | Start Rule + 4 Minimum |
|---|---|---|---|
| All QBs: chance of 1+ starter season | 0.057 vs 0.045 ✗ | 0.063 vs 0.046 ✗ | **0.047 vs 0.045 ✗ (just)** |
| All QBs: expected starter seasons | 0.157 vs 0.103 ✗ | 0.152 vs 0.104 ✗ | **0.129 vs 0.100 ✗** |
| Few real games: chance of 1+ | 0.047 vs 0.046 ✗ | 0.066 vs 0.050 ✗ | **0.033 vs 0.046 ✓** |
| Few real games: expected | 0.085 vs 0.094 ✓ | 0.110 vs 0.104 ✗ | **0.064 vs 0.091 ✓** |
| Miss size, all QBs (Brier, lower is better) | 0.1293 | 0.1280 | **0.1264** |

**Said vs happened, all QBs (the card's own shares):**

| Share | Said (All Three) | Happened |
|---|---|---|
| Two or more starter seasons | 29–30% | 25% |
| One starter season | 11% | 11% |
| None | 59–60% | 64% |

**What it means.**

- **The card is a little too rosy on QBs in every version.** It says about 30% get two or more starter seasons; 25% did.
- **The start rule on its own makes the few-games QBs worse.** That is the Willis problem.
- **The start rule + 4-game minimum is the best of the three on every check and on miss size,** and it is honest for
  QBs with few real games. It still misses narrowly on all QBs.
- **This is a tougher test than 1 Nov's.** That one was graded on fresh 2021–22 rows, with the per-position check at the
  99.4th percentile. This one is 2013–2022, QBs only, at the 95th. On 2 Nov, Version A (draft dropped from career year
  2) was already "honest, narrowly".
