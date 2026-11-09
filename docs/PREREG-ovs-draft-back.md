# PRE-REGISTRATION — Own Value Scale: Draft Pedigree Back For Veterans, Fading With Games

**Drafted:** 8 November 2026. **Status: DRAFT, NOT LOCKED.** Steve: "yes please let's do the draft pedigree section.
Though I am very interested to see how that impacts Puka and Purdy." Locks by committing this document with
`study/ovs_draft_back.py` and its crash results, before the one real run.

---

## Plain-English Summary (For Steve)

**Today:** draft slot stops counting completely from a player's second season (your call on 2 November, tested in
`PREREG-draft-drop.md`).

**The change:** draft slot counts for every veteran, but fades as he plays. It counts in full with no games, half at 24
career games and a quarter at 72. A proven late-rounder like Puka or Purdy barely feels it. A journeyman with few real
games, like Malik Willis, feels it a lot. This was the rule before 2 November.

**The test:** for veterans in their second season or later, 2013–2022, does it predict their next three seasons at
least 2% better?

## 1. The Change, And Only The Change

- **Base:** the adopted preseason value, meaning era-adjusted matching, three seasons ahead, offseason features, with games
  out of matching (`DECISION-no-games-in-matching.md`). Draft weight is 0 from career year 2 (`comps_draft_drop` mode
  A).
- **New:** veteran draft weight 1.5 × 24 ÷ (career games + 24) at every career year (`DD.CUT['A']` 2 → never). Nothing
  else changes. The script asserts that no row outside career year 2+ gets new matches.
- **Rows decided on:** veteran test rows in career year 2 or later.

## 2. The Questions

- **Decides:** RMSE on FV3 over those rows, new vs base. It must be at least **2% better**, with paired permutation
  p < 0.05 (a player's rows together, 10,000 shuffles); **and** all rows no more than 0.5% worse; **and** close synthetic
  trades no more than 1.0 point worse.
- **Decision:** passes → veterans keep the fading draft weight, preseason and in-season (Steve's OK). Fails → draft stays
  out from career year 2.

## 3. Reported, Deciding Nothing

- By position.
- Veterans with fewer than 24 career games (the journeyman group): accuracy, and what they produced ÷ each value.

## 4. Prior Looks

- **`PREREG-draft-drop.md`** (five-season outcome, the older matching): dropping draft from year 2 was 0.5% better on the
  rows it changed (p = 0.25). It is the same comparison on an older setup, in the other direction.
- **Today's page with the change** (8 Nov, uses no outcomes):
  - Puka 6 → 8, Purdy 7 → 9, Willis 43 → 89, Maye 2 → 7, Burrow 9 → 17, Goff 22 → 31.
  - Nabers 13 → 6, Bowers 36 → 43, Caleb Williams 12 → 18, Baker Mayfield 77 → 61.
  - Position averages unchanged.
- The base value's overall results are known.

## 5. Crash Tests, Before Lock

The era study's worlds with this rule: noise passes in at most 1 of 20; planted w = 0.75 passes in ≥ 80% of 200; w = 0.6
reported. If the planted world fails, this goes to Steve before any real run.

## 6. Limits

- One fade (the old 24-game rule), not tuned.
- Matching is within position, so this can reorder players at a position but cannot change the balance between
  positions.

## 7. Not Licensed Here

The DELTA Score, the site's model value, buy/sell calls. Nothing on the site changes.

## 8. Amendments

(None yet.)
