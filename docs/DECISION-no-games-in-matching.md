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

## 4. Results (8 Nov 2026, Run Once)

`study/out/ovs_no_games_results.json`.

| | Preseason (6,484 rows) | Week 9 (6,808 rows) |
|---|---|---|
| Typical miss, with games → without | 50.68 → 50.54 (**0.3% better**, p = 0.21) | 47.61 → 48.88 (**2.7% worse**) |
| Close trades called right | 55.3% → 54.6% (0.7 points worse) | 58.1% → 51.3% (**6.9 points worse**) |
| "Missed time" rows: produced ÷ predicted | 87% → 79% (3,203 rows, ≤ 10 games) | 74% → **50%** (4,216 rows, ≤ 5 games) |
| Everyone else: produced ÷ predicted | 93% → 96% | 92% → 106% |

By position, week 9: QB −3.8%, RB −2.3%, WR −2.3%, TE −0.6%. Preseason: QB +0.9%, RB +0.3%, WR −0.2%, TE −0.5%.

**What it means.**

- **Preseason:** removing games costs nothing.
- **Week 9:** removing games costs a lot. Most of the "missed time" rows are not injured starters: 62% of all week-9
  rows have five or fewer games, so they are mostly backups, cut players and practice-squad players. For them, "games so
  far" carries a real message: he isn't on the field. With games removed, their values sit at twice what they went on
  to produce.
- **So in-season games does two jobs.** One is the injury penalty DELTA forbids. The other is a legitimate "does he have
  a job" signal. Removing the column removes both.

**Today's page (week 9, full PPR, 12-team superflex, without games):**

- Agreement with FantasyCalc's top-150 order rises from 0.78 to 0.81.
- Average rank by position (market in brackets): QB 57 (60), RB 87 (76), WR 71 (79), TE 96 (90). With games it was QB
  57, RB 99, WR 88, TE 124.
- Player moves:
  - Caleb Williams 25 → 18
  - Drake Maye 2 → 10
  - Burrow 7 → 11
  - Malik Willis 36 → 65
  - Bowers 40 → 35
  - McBride 22 → 25 and Goff 21 → 26, so McBride is now ahead
  - A.J. Brown 161 → 240
  - Charbonnet 346 → 222

**Distinctness check (reported, deciding nothing).** Within position, among the market top 150:

| Comparison | Rank agreement |
|---|---|
| New value vs FantasyCalc | 0.82 |
| New value vs DELTA Score | 0.66 |
| FantasyCalc vs DELTA Score | 0.73 |

The new value sits closer to the market than to the DELTA Score, and further from the Score than the market itself is.

**Next (Steve's call).** An injury-neutral version of games: weeks out hurt count as available; weeks cut, on the
practice squad, a healthy scratch, suspended or off a roster still count as missed. Preseason stays without games.
