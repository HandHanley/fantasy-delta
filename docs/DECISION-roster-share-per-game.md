# DECISION — Own Value Scale: Roster Share Counts Points Per Game

**Drafted:** 12 November 2026. **Status: DECIDED BY RULE, measured once.** Steve, 12 Nov: "Yes we should set that up -
that seems wrong." Committed before the measurement runs.

---

## Plain-English Summary (For Steve)

**What it was.** The preseason value (adopted 8 Nov, `PREREG-ovs-offseason.md`) matches each veteran on his **roster
share**: his points last season ÷ the points of everyone at his position on his new club. It used his season **total**.
A running back who missed half the year hurt looked like he had half the role, and was matched with backups. That is a
games-missed penalty, which DELTA does not allow.

**What changes (v2, see §5).** Weeks he missed **hurt** are filled in at his own rate: his points per available game ×
(available weeks + weeks out hurt). It uses the same available and hurt rules as the adopted in-season value. Healthy
weeks he didn't play stay zeros, so a backup isn't promoted. Teammates' totals are unchanged. A player who was never
hurt is unaffected.

**Why this isn't a test.** DELTA's rule forbids an availability penalty, so the change is made whatever it costs. We
measure the cost so it's on the record, as we did when games came out of matching (`DECISION-no-games-in-matching.md`).

## 1. The Change, And Only The Change

- **Roster share:** his season-`t` points → his points + (points ÷ available weeks) × weeks out hurt. The group total
  swaps his actual points for the rescaled ones.
- **Unchanged:** draft capital, every other feature and weight, the 30 matches, pool, recency weighting, FV3, rookies.
  Games out of matching (8 Nov) stays.
- **Known limit:** teammates who filled in while he was out keep those points, so his share is still a little low. A
  cleaner fix would need week-by-week shares. Fine for now; noted.
- **Checked in code:**
  - With no rescaling, the new function reproduces today's share exactly.
  - The adopted value reproduces `ovs_no_games.py` re-run on the same data (50.534; the 8 Nov file reads 50.536, a
    data refresh).
  - Rookie matches are unchanged.

## 2. Measured, Deciding Nothing

`study/ovs_share_per_game.py`, results in `study/out/ovs_share_per_game_results.json`. Test seasons 2013–2022, the
adopted preseason value's rows:

- typical miss (RMSE, FV3), all rows and by position, with p (a player's rows together);
- close synthetic trades;
- produced ÷ value for players who missed time (10 or fewer games), players who didn't, and rows whose share changed;
- the largest share changes, by name.

## 3. Prior Looks

The adopted value's results are known. No per-game share has been compared with any outcome.

## 4. Live Use

The in-season value (week 5 on) doesn't use roster share. This takes effect when the preseason value is next used:
after the season, for March free agency.

## 5. Results (12 November 2026) And One Correction

**v1, as first written (`out/ovs_share_per_game_results_v1_all_games.json`), superseded.** "Points per game × club
games" also rescaled healthy backups who simply didn't play: Brian Hoyer, Sam Howell and Matt Barkley, one game each,
jumped from about 10% to 60–70% share. That's a bonus for not playing, not injury neutrality. It cost 0.4% overall and
1.6 points on close trades, and players who missed time produced only 65% of their raised values. **The check should
have been:** "does this treat a healthy scratch like an injury?", asked before running, using the available-games rule
the in-season value already has. The rule was corrected to v2 on that principle, not on its result.

**v2, the rule (`out/ovs_share_per_game_results.json`):**

| Check | Today | Per-Game Share (v2) |
|---|---|---|
| Typical miss, all 6,484 rows | 50.53 | 50.54 (0.01% worse, p = 0.52) |
| Close trades called right (23,313) | 55.5% | 55.3% (0.2 points worse) |
| Players who missed time (10 or fewer games): produced ÷ value | 79% | 70% |
| Players who didn't miss time | 96% | 96% |

- **By position:** QB 0.2% better, RB 0.1% better, WR 0.2% worse, TE 0.8% worse.
- **Rows whose share changed:** 1,645 of the test rows (2,568 across all seasons).
- **Largest changes:** David Johnson 2017 (hurt after week 1) 27% → 85% share, value 80 → 183. Delanie Walker 2018,
  Saquon Barkley 2020 and Cam Newton 2019 move the same way.

**What it means.** Removing the penalty costs nothing in accuracy. Players coming off an injury now sit higher than what
history says they produced (70% of value), the same kind of gap the no-games decision left on 8 Nov. That's the price of
DELTA's rule, and it's on the record.

**Adopted:** the preseason value uses the v2 share (by rule; Steve's instruction 12 Nov).
