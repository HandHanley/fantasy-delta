# Research — Wins Added As The Value Yardstick (Descriptive, 8 Nov 2026)

**Question (Steve, 8 Nov):** running backs and tight ends are scarce, in the NFL and in lineups; elite ones win
championships. Does a weekly, scarcity-aware yardstick credit them more than "points above the season's starter line"?

**What was built** (`study/wins_added.py`). For each regular-season week a player played: how much he raised a typical
team's chance of winning that week against that week's replacement at his position (the Nth-best score that week:
QB 24, RB 30, WR 42, TE 14), with the team's weekly spread measured each season (about 23–24 points). A season's wins
added = the sum over his weeks, floored at zero. Half PPR + TE premium, nflverse weekly files 1999–2025.

**Nothing here predicts anything; no test was run.** It describes past seasons only.

## What It Found

**The two yardsticks order seasons similarly** (rank agreement 0.80–0.84 among players with value).

**But wins added moves value toward QBs and away from tight ends.** Share of all value, by position:

| Season | QB: Wins Added / Points Above Line | RB | WR | TE |
|---|---|---|---|---|
| 2015 | 37% / 29% | 23% / 20% | 34% / 38% | **7% / 13%** |
| 2020 | 38% / 38% | 28% / 24% | 29% / 31% | **5% / 7%** |
| 2025 | 34% / 28% | 30% / 32% | 31% / 32% | **5% / 8%** |

Why: most tight end weeks sit near replacement, and a win-probability yardstick gives a huge week less extra credit
than raw points do. Running backs come out about the same.

**An elite RB season is already worth more than an elite QB season, on either yardstick.** 2025: Christian McCaffrey
2.60 wins added, Josh Allen 2.28; RB1 cleared his line by 229 points, QB1 by 191.

## What It Means

- The gap between DELTA's values and the market at RB and TE is **not** about how a season is scored. It's about the
  forecast: how often an elite RB or TE season repeats over the next three years. History (the Own Value Scale's
  matches) says less often than the market prices; DELTA's own calibration agrees (2013–2022, RBs went on to produce
  81% of their value, TEs 99%).
- Whether the market's confidence is right is the head-to-head question (market vs DELTA at predicting the next three
  seasons), not a yardstick question.
- **Recommendation:** keep points above the starter line (simpler, and wins added would push tight ends down). Not
  adopted.
