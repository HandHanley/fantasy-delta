# DECISION — Own Value Scale: Games Played Comes Out Of Matching

**Drafted:** 8 November 2026. **Status: DECIDED BY RULE, measured once.** Steve: "I want to first remove the games played
from matching." Committed before the measurement runs.

---

## Plain-English Summary (For Steve)

**What it was.** Each veteran is matched with past players on five things: production, age, draft slot, career year,
and **games played** (last season, or so far this season). A player who missed time was compared with past players who
missed time, and they tended to produce less afterwards. That is a games-missed penalty, which DELTA does not allow.

**What changes.** Games played is dropped from matching. The other four, plus the offseason items (roster share, draft
capital), are unchanged.

**Why this isn't a test.** DELTA's rule forbids an availability penalty, so the change is made whatever it costs. We
still measure the cost so it's on the record, not so it can overturn the decision.

## 1. The Change, And Only The Change

- Veteran matching weight on `games` goes from 1.0 to 0 (`C.W_V['games']`). Every other feature, weight, the 30
  matches, the pool, the recency weighting and the outcome (FV3) are unchanged.
- Applies to the preseason value (`ovs_offseason.py`, the adopted value) and the in-season value (`ovs_in_season.py`).
- **Left alone, on purpose:**
  - Production stays points per game over the seasons he played.
  - The draft-slot fade uses career games as a measure of experience, not missed time.
  - The outcome counts what a player actually scored over the next three seasons. That is the measuring stick, not a
    lever on his value.

## 2. Measured, Deciding Nothing

Test seasons 2013–2022, same rows as the adopted value. `study/ovs_no_games.py`, results in
`study/out/ovs_no_games_results.json`.

- Preseason: typical miss (RMSE, FV3), all rows and by position, with and without games; paired permutation p (a
  player's rows together); close synthetic trades called right.
- In-season, week 9: the same, against the in-season value.
- **Players who missed time** (preseason: 10 or fewer games in the snapshot season; week 9: 5 or fewer games so far):
  what they went on to produce ÷ what each version predicted. This shows the size of the penalty that's been removed,
  and how far these players' values now sit above what history says.
- Today's week-9 values (full PPR, no TE premium) with and without games: rank changes, including Caleb Williams,
  A.J. Brown and Zach Charbonnet.

## 3. Prior Looks

The adopted value's results are known. On 8 Nov the week-9 page was eye-tested and games played was suspected for Caleb
Williams, A.J. Brown and Charbonnet. No without-games prediction has been compared with any outcome.

## 4. Results

(Filled in after the one run.)
