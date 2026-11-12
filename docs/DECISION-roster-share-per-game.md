# DECISION — Own Value Scale: Roster Share Counts Points Per Game

**Drafted:** 12 November 2026. **Status: DECIDED BY RULE, measured once.** Steve, 12 Nov: "Yes we should set that up -
that seems wrong." Committed before the measurement runs.

---

## Plain-English Summary (For Steve)

**What it was.** The preseason value (adopted 8 Nov, `PREREG-ovs-offseason.md`) matches each veteran on his **roster
share**: his points last season ÷ the points of everyone at his position on his new club. It used his season **total**.
A running back who missed half the year hurt looked like he had half the role, and was matched with backups. That is a
games-missed penalty, which DELTA does not allow.

**What changes.** His own points become **his points per game × his club's games that season** (16 through 2020, 17
from 2021): what he'd have scored playing every game at his rate. Teammates' totals are unchanged. A player who played
every game is unaffected.

**Why this isn't a test.** DELTA's rule forbids an availability penalty, so the change is made whatever it costs. We
measure the cost so it's on the record, as we did when games came out of matching (`DECISION-no-games-in-matching.md`).

## 1. The Change, And Only The Change

- **Roster share:** his season-`t` points → points per game × season games, never below what he actually scored. The
  group total swaps his actual points for the rescaled ones.
- **Unchanged:** draft capital, every other feature and weight, the 30 matches, pool, recency weighting, FV3, rookies.
  Games out of matching (8 Nov) stays.
- **Known limit:** teammates who filled in while he was out keep those points, so his share is still a little low. A
  cleaner fix would need week-by-week shares. Fine for now; noted.
- **Checked in code:**
  - With no rescaling, the new function reproduces today's share exactly.
  - The adopted value reproduces its recorded accuracy (50.536).
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
