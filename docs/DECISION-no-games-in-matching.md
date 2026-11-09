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
- Average rank by position, rank among all valued players (market in brackets): QB 62 (60), RB 107 (76), WR 84 (79),
  TE 121 (90). With games it was QB 57, RB 99, WR 88, TE 124. *(Corrected 8 Nov: the first version put the no-games
  ranks within the top 150 next to the others' ranks among all players, which made TEs look about 28 places higher
  than they were.)*
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

## 5. Amendment: Injury-Neutral Games In-Season (8 Nov 2026, Before Its Run)

Steve: "Yeah let's do both." Committed before this run.

**The rule.** In-season, "games so far" becomes **games played + weeks out hurt**, never above the week number.
Code: `study/injury_weeks.py`. A week counts as out hurt when his club played that week, he recorded no pass, carry,
target or catch, and either:

- **he was on a reserve list** (weekly roster status RES, PUP or RSN). How that reads depends on the season's file:
  - **2016 onward:** the files are week by week, so his status that week is used.
  - **2002–2015:** the weekly files carry one end-of-season status and drop players once they go on injured reserve,
    so every week after his last listing counts when that last listing is a reserve status. A season counts as this
    older style when more than 5% of its reserve listings fall in weeks he played (about half do before 2016, none
    after). That is set by the file format, not by any outcome.
- **or, from 2009, the official injury report** (nflverse) listed him Out or Doubtful that week.

Weeks cut, on the practice squad, a healthy scratch, suspended, on the exempt list or off a roster still count as
missed. The rule is about injuries.

**Checked by hand before any outcome was read (through week 9):**

| Player | Season | Weeks Out Hurt | What Happened |
|---|---|---|---|
| Dez Bryant | 2015 | 5 | Missed weeks 2–6, foot |
| Le'Veon Bell | 2015 | 1 | Hurt in week 8, so week 9 counts; his suspension weeks don't |
| Jamaal Charles | 2015 | 3 | Torn ACL in week 5 |
| Christian McCaffrey | 2020 | 6 | Missed weeks 3–8 |
| Saquon Barkley | 2020 | 7 | Torn ACL in week 2 |
| Adrian Peterson | 2014 | 0 | Exempt list, not an injury |
| Josh Jacobs | 2026 | 0 | Exempt list, weeks 1–6 |

**Known gap.** The 2002–2015 files leave out players who spent the whole season on injured reserve (Jordy Nelson 2015),
so those still count as missed. Short game-day inactives before 2009 can't be told apart from healthy scratches.

**Decision, set now.**

- In-season matching uses injury-neutral games.
- Fallback: if it is worse than no games at all on both the typical miss and close trades, in-season uses no games.
- Preseason stays without games (§4: removing it there costs nothing).
- Either way, no injury penalty.

**Measured (week 9, 2013–2022, same rows as §4), deciding nothing beyond the line above:**

- Typical miss and close trades: injury-neutral vs with games (the cost of the rule, done precisely) and vs no games.
- Players with 2+ weeks out hurt: produced ÷ predicted. This is the size of the penalty removed.
- Low-games players never hurt (5 or fewer games, 0 weeks out hurt): produced ÷ predicted. This is the "does he have a
  job" signal, kept.
- Today's page, rebuilt.

### Results (8 Nov 2026, Run Once)

`study/out/ovs_injury_games_results.json`. **Decision line: injury-neutral games in-season** (the fallback did not trigger).

| Week 9 (6,808 rows) | Typical Miss | Close Trades Called Right |
|---|---|---|
| Injury-neutral vs with games | 48.07 vs 47.61 (**1.0% worse**) | 54.1% vs 56.9% (2.8 points worse) |
| Injury-neutral vs no games | 48.07 vs 48.88 (**1.7% better**, p = 0.0007) | 57.8% vs 52.7% (5.1 points better) |

Each comparison builds its own close trades, so the trade figures differ between rows. By position, injury-neutral vs
with games: QB −0.3%, RB −1.6%, WR −1.5%, TE −0.5%. 1,455 rows have at least one week out hurt.

**What each group went on to produce, as a share of its value:**

| Group | With Games | No Games | Injury-Neutral |
|---|---|---|---|
| 2+ weeks out hurt (986 rows) | 99% | 81% | 69% |
| 5 or fewer games, never hurt (3,176 rows) | 53% | 33% | 55% |

- **Players who've been out hurt:** historically they produced less afterwards, and the old games count priced that in
  almost exactly. They are now valued at what healthy comparables went on to do, about 45% above their own history. That
  is the price of DELTA's rule, paid deliberately.
- **Players short on games without being hurt:** the "does he have a job" signal is kept.

**Today's page (week 9, full PPR, 12-team superflex):**

| Player | Weeks Out Hurt | With Games | Injury-Neutral |
|---|---|---|---|
| Caleb Williams | 2 | 25 | **12** |
| Zach Charbonnet | 7 | 346 | 220 |
| Alec Pierce | 6 | 323 | 128 |
| Jaxson Dart | 5 | 113 | 30 |
| A.J. Brown | 4 | 161 | 203 |
| Brock Bowers | 2 | 40 | 36 |

- **Healthy players:** close to where they were with games (Maye 2, Burrow 9, Malik Willis 43, Goff 22, McBride 24).
- **The bigger shifts in §4 came from somewhere else.** Without games, Maye was 10th and Willis 65th. Those
  moves came from dropping games for healthy players, not from the injury fix.
- **Position balance (average rank in the market top 150, rank among all valued players, market in brackets):** QB 49
  (60), RB 102 (76), WR 86 (79), TE 121 (90). QBs sit higher than with games (57), the opposite of what's wanted.
- **Agreement with FantasyCalc:** 0.81 (with games 0.78).

**Why A.J. Brown falls:** he has 3 games and 4 weeks out hurt, so he is now matched with healthy receivers on his
production this season.
