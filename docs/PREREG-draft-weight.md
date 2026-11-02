# PRE-REGISTRATION — Comparables: Give Draft Slot The Weight K = 24 Implies

**Drafted:** 2 November 2026, before any result exists. **Status: LOCKED** by the commit that adds it
with `study/comps_draft_weight.py` before the real run.

## Plain-English Summary

On the mock cards, Brock Bowers (pick 13, 29 career games) was matched with tight ends picked 85th, 95th and 113th. The
reason: in the comparables formula, draft slot carries only about 8% of the matching weight at 29 games. The August
finding (K = 24) says that at 29 games, a young player's own production and his draft slot should share the job about
55 / 45. The 8% was a translation choice made on 1 Nov, never fitted.

**The test:** a version that splits the production weight between production and draft slot exactly as K = 24 says, then
check (1) is it at least as accurate as today's version, and (2) are its odds still honest?

## 1. Prior Looks — Disclosure

- The idea came from how a mock card **looked** (who the matches were), not from any accuracy or odds result.
- Today's version's accuracy on the 2013–2020 test set is known (1 Nov; roster-position run: RMSE 73.9). The new
  version's has never been computed. Today's version's three-year odds on 2021–22 and 2009–12 are known; the new
  version's are not.

## 2. The Two Versions

Both are the 1 Nov comparables method (veterans with veterans, rookies with rookies, 30 nearest, z-scored within position
from the pool, roster positions). Rookies are **identical** in both (draft 3, age 1). Only veterans' weights differ.
`G` = his career games.

| Feature | Today | K = 24 Version |
|---|---|---|
| Recent production | 3 | 3 × G / (G + 24) |
| Draft slot | 1.5 × 24 / (G + 24) | 3 × 24 / (G + 24) |
| Age | 2 | 2 |
| Year in the league | 1 | 1 |
| Games last season | 1 | 1 |

At 29 games the K = 24 version gives production 1.64 and draft 1.36; at 94 games, 2.39 and 0.61; at 8 games, 0.75 and
2.25. Nothing is fitted.

## 3. Questions And Bar

**Q1 — Accuracy (five-year value, the 1 Nov test set: all 4,948+ snapshots, 2013–2020, pool ≤ t − 5).** The K = 24 version
passes if its RMSE is **no more than 1% worse** than today's, both overall and on veterans in years 1–3 (the players it
changes most). Reported: the lift, a player-clustered permutation p-value, MAE and rank agreement.

**Q2 — Odds (three-year, Fix 2 weights, the fresh 2021–22 set, pool ≤ t − 3).** The K = 24 version's odds must be
honest under the same A6 rule. 2009–12 reported, deciding nothing.

**Decision.** Both pass → the K = 24 version replaces today's for the cards (Steve's OK still needed to show anything).
Q1 fails → today's weights stay and the card says veterans are matched mostly on production. Q1 passes but Q2 fails →
reported; no switch.

**Also reported (display only):** each mock player's draft-pick range of matches under both versions.

## 4. Checks Before Lock

1. **Same code, same answer:** the new script run with today's weights must reproduce `comps_value_study.precompute`'s
   30 neighbours exactly, row for row, on every test snapshot. Any difference stops the study.
2. **Leak checks** asserted as before: pools ≤ t − lag; nobody in his own pool.
3. **Size note:** Q1 is a point-estimate rule, not a significance test, so it needs no planted-world power check; the
   permutation p and a bootstrap range are reported so a "too close to call" result is visible.

## 5. Amendments

### Pre-lock (2 Nov 2026)

- **A1. Equivalence check passed.** With today's weights, the new script's neighbours match
  `comps_value_study.precompute` exactly: 5,034 of 5,034 rows (five-year, 2013–2020) and 1,359 of 1,359 (three-year,
  2021–22), zero mismatches. (5,034 is the roster-position count from the 1 Nov post-lock run; the locked run had 4,948.)

### Results (2 Nov 2026) — `study/out/comps_draft_weight_results.json`

**Decision under the locked rule: keep today's weights.** Q1 failed on veterans in years 1–3, and Q2 failed.

| Group | Today's Miss (RMSE) | K = 24 Version | Change | Bar |
|---|---|---|---|---|
| All 5,034 test snapshots | 73.9 | 74.1 | 0.3% worse | ≤ 1% worse: pass |
| Veterans, years 1–3 (2,144) | 73.8 | 74.7 | **1.2% worse** | ≤ 1% worse: **fail** |
| Veterans, year 4+ (2,258) | 69.9 | 69.4 | 0.7% better | reported |
| Rookies (632) | 87.3 | 87.3 | identical (unchanged by design) | — |

95% ranges on the change are wide (all: 0.9% better to 1.3% worse; years 1–3: 0.8% better to 3.0% worse), so the two
versions are close; the K = 24 version comes out behind exactly where it was meant to help. Rank agreement moved
slightly up (0.567 → 0.570 overall).

**Q2 (odds, fresh 2021–22): not honest** (overall P3 0.033 vs limit 0.028; WR P3 0.053 vs 0.049), though its Brier score
was a touch lower (0.0788 vs Fix 2's 0.0797). 2009–12 (reported): not honest (QB P3).

**What it does to the cards (display only):** matches look more sensible: Bowers picks 6–42 (was 6–113), Lamb 7–54 (was
4–84), Harrison 2–13 (was 2–16). Javonte Williams still reaches pick 100 (running backs drafted late are common matches).

Stated plainly: **the matches looked wrong, but the predictions were not.** Leaning on draft slot more makes the lists read
better without making them more accurate, and it costs the odds their honest rating.
