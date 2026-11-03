# PRE-REGISTRATION — Comparables: Drop Draft Slot After Two Seasons

**Drafted:** 2 November 2026, before any result exists. Steve approved running without reviewing parameters ("Sure yeah,
let's just set it up and run it", 2 Nov). **LOCKED** by the commit that adds this file with `study/comps_draft_drop.py`.

## Summary

Earlier today (`docs/PREREG-draft-weight.md`) giving draft slot *more* weight failed. Steve's view: once a player has two
seasons of NFL data, draft slot shouldn't be part of the match at all, so the card can drop the draft row. This tests
whether removing it from the matching costs accuracy or honest odds.

## Versions (veterans only; rookies and everything else unchanged)

- **Today:** draft weight `1.5 × 24 / (G + 24)`.
- **Version A:** draft weight **0** once the player has **two or more seasons** on record (career year ≥ 2 at the
  snapshot); today's weight before that.
- **Version B:** draft weight **0** from career year ≥ 3; today's weight before that.

Nothing fitted. Same code path as `study/comps_draft_weight.py` (equivalence re-checked in this script).

## Bar (each version on its own)

- **Q1, accuracy** (five-year value, 2013–2020, roster positions): RMSE no more than **1% worse** than today's, overall
  **and** on the veterans whose weights change.
- **Q2, odds** (three-year, Fix 2 weights, fresh 2021–22): honest under the A6 rule. 2009–12 reported only.
- A version passes if both pass. If both versions pass, **A** is used (Steve's line). If neither passes, today's weights
  stay and the card lists draft pick last for veterans.

Disclosure: today's version's numbers on these sets are known; neither new version's are. Motivation is card design, not
any result.

## Amendments

- **A1 (pre-result).** The locked script (`e363bc1`) crashed before computing anything (its weight hook called itself).
  Fixed by computing the veteran weights directly in the loop; no rule changed. The equivalence check still runs first.

## Results (2 Nov 2026) — `study/out/comps_draft_drop_results.json`

**Decision under the rule: Version A** (draft slot drops out once a player has two seasons on record). Both versions passed.
Equivalence check: today's weights through this script matched `precompute` on all 5,034 rows.

| | Version A (2+ seasons) | Version B (3+ seasons) |
|---|---|---|
| Accuracy, all 5,034 | 0.4% **better** (73.7 vs 73.9) | 0.5% better (73.5) |
| Accuracy, veterans it changes | 0.5% better (3,664) | 1.0% better (2,920) |
| Is the gain clearly real? | No (p = 0.25) | No (p = 0.09) |
| Odds honest, fresh 2021–22 | **Yes** | Yes |
| Odds miss (Brier), fresh 2021–22 | 0.0816 (today 0.0797) | 0.0807 |
| Odds honest, 2009–12 (reported) | No (overall E3) | No (overall E3) |

Stated plainly: dropping draft slot did not cost accuracy; both versions came out slightly ahead, within noise. B edged A on
every measure, but the rule named A ahead of time and the gaps are small. Both versions' odds are a touch less sharp than
today's (Brier about 1–2% higher) and, unlike today's, fail one check on 2009–12, so the odds remain "honest, narrowly".

