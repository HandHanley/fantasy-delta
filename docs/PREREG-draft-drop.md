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

## Results

_Filled in after the single run._
