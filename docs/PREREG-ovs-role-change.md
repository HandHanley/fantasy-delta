# PRE-REGISTRATION — New Value: A Player Whose Role Grew Is Judged On His New Role

**Drafted:** 25 November 2026, before any role-change value has been built or compared with any outcome. **Status:
LOCKED** by committing this document with `study/ovs_role_change.py`. Crash tests run next; the real run only if they
pass. Steve, 25 Nov: "yeah let's do the role change plan and see what that gives us" (plan put to him 13 Nov).

---

## Plain-English Summary (For Steve)

**The problem.** A player's production blends three seasons: this season counts 3 parts, last season 2, the one
before 1. Bhayshul Tuten is averaging 15.9 points a game as Jacksonville's starter; his 5.6 as a rookie backup still
counts for 2 parts.

**The rule being tested.** If a player's share of his team's carries plus targets now ranks him among the starters at
his position, and last season his share was well under that, only this season's production counts.

**The test.** On 2013–2022 players at week 9, judged on the players the rule applies to: at least 2% better, with the
usual luck check, and it can't make everyone else more than 0.5% worse. Crash tests first.

## 1. The Role-Change Flag (Usage Only, No Outcomes)

From the weekly stats files (regular season), for a player at season Y, week 9:

- **Share** = his carries + targets ÷ his team's carries + targets, summed over the team-weeks he played. This season:
  weeks 1–9. Last season: the full season.
- **Flagged** when all of these hold:
  - he's a **RB, WR or TE** (QBs are handled by the QB starts rule);
  - **4+ games** this season (to week 9) and **4+ games** last season;
  - this season's share ranks him **inside the starter line at his position** among every player with 4+ games this
    season: top **34 RBs, 48 WRs, 14 TEs** (the adopted starter lines);
  - last season's share was **under two-thirds** of this season's;
  - **Y ≥ 2010.** Targets are recorded as zero before 2009, so earlier seasons can't be measured; their rows are never
    flagged.
- **Only a role that grows.** A shrinking share is often a player playing through an injury; acting on it would be an
  injury penalty.

## 2. The Change

- For a flagged row, the in-season production used in matching is **this season's only** (the same per-available-game,
  era-adjusted figure as today's this-season part). Last season's and the one before drop out.
- Applied to every row in the frame, past matches included, so the comparables are measured the same way.
- Nothing else changes: the 30 matches, weights, recency, the incoming-rookie value and the 150-snap rookie rule.

## 3. Frame And "Today"

`ovs_small_samples` (week 9, test rows 2013–2022, outcome FV3 in the study scoring) and "today" = the live build
(in-season value, rookies under 150 snaps or with no game on their incoming-rookie value), exactly as
`PREREG-ovs-one-match.md` §1. Its reproduction check must pass. The rebuilt frame must reproduce today's production for
every unflagged row.

## 4. Decision

- **Decided on:** test rows that are flagged and not on the incoming-rookie value.
- **Passes** if the rule's RMSE on those rows is at least **2% lower** than today's, with paired permutation p < 0.05
  (10,000 shuffles, a player's rows together), **and** RMSE on all test rows is at most **0.5% worse**.
- **Passes →** the weekly build uses it (Steve's OK first). **Fails →** no change.

## 5. Crash Tests, Before Any Real Run

- **Noise:** outcomes shuffled within position and season; both values rebuilt from the shuffled outcomes on their own
  matches. May pass at most 1 of 20.
- **Planted (match draw, as `PREREG-ovs-one-match.md` §3):** each player "becomes" one of his own 30 matches, drawn by
  match weight. Rule-is-right world: drawn from the rule's matches. Must pass at least 80% of 200. Today-is-right world:
  drawn from today's matches; reported (50 runs).
- **If either fails,** this goes to Steve before any real run.

## 6. Reported, Deciding Nothing

- Flagged rows by season and position, and how many test rows' values move.
- By position on the flagged rows.
- Produced ÷ value on the flagged rows, today and the rule.
- Rank correlation with the outcome on all test rows.
- **This week's build either way:** the flagged players, and what the rule would do to them.

## 7. Prior Looks

On 13 Nov, feature-only counts (no outcomes): under an earlier version of the flag (ranked among players with 4+
games in both seasons), 384 flagged rows 2006–2022, inflated before 2010 by missing targets; 15 flagged 2026 players at
week 9 (Tuten, Likely, Hubbard, Walker, Golden, Burden, Braelon Allen, DeVonta Smith and others). **No role-change
value has been compared with any outcome.**

## 8. Limits

- About 150–200 flagged test rows: a small group, so the crash test may show the 2% bar can't see a realistic effect.
- The flag can't see a role that hasn't happened yet (Trevor Etienne, 5% share). DELTA counts demonstrated production.
- Team carries + targets mix rushing and receiving roles: a slot receiver and a lead back are measured on one scale.
  The starter-line rank is within position, so they aren't compared with each other.
