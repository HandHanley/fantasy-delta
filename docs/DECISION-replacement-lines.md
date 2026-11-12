# DECISION — Where Should The Lines Be? (12-Team Superflex)

**Drafted:** 12 November 2026, before any allocation was run. **Status: MEASUREMENT; the decision is Steve's.** Steve, 12
Nov: "should QB24 REALLY be the bar we're setting for a usable QB? … yep let's do the lines".

---

## Plain-English Summary (For Steve)

**What the lines are.** Every DELTA value is "points above the last starter": QB24, RB30, WR42 and TE14 in a 12-team
superflex league. A player scoring at the line is worth zero, and everything above it is value. Move a line and every
player at that position gets worth more or less.

**Where they came from.** A standard lineup (1 QB, 2 RB, 3 WR, 1 TE, 2 flex, 1 superflex), with a fixed guess at how
the flex and superflex spots split between positions. Nobody measured the split.

**What this does.** For every season 2002–2025, fill 12 teams' starting lineups with the best available players, flex
and superflex included, and count how many of each position end up starting. That count is where the line belongs.

## 1. The Lineup

- **DELTA's (decides):** QB 1, RB 2, WR 3, TE 1, Flex (RB/WR/TE) 2, Superflex (QB/RB/WR/TE) 1; 12 teams, 120 starters.
- **Reported:** a common 2-WR version (QB 1, RB 2, WR 2, TE 1, Flex 2, Superflex 1; 108 starters).

## 2. Two Ways To Fill The Lineups

- **A. Season totals (decides).** Rank players by season points. Fill each position's own slots with its best players,
  then the flex spots with the best remaining RB/WR/TE, then the superflex spots with the best remaining player at any
  position. This is the same season-total footing the lines are used on (`comps_value_study.REPL_N`: the Nth-best
  season total).
- **B. Week by week, using only what was known (reported).** For each week from week 2, rank players who played that
  week by their points per game in the season's earlier weeks, fill the lineups the same way, and count starters by
  position. Averaged over the season. This is closer to how managers actually set lineups, because they don't know
  the future.

## 3. Scoring

- **Half PPR + TE premium (decides):** DELTA's study scoring, which the lines are used with.
- **Full PPR, no TE premium (reported):** the display scoring.

## 4. What's Reported

- The average number of starters per position, by method and scoring, for 2002–2025 and the last five seasons
  (2021–2025).
- The points of the last starter at each position (the line) vs today's lines.
- The next-best player left out at each position (who'd fill a flex or superflex spot instead).

## 5. Prior Looks

On 12 Nov, before this was written, Claude pulled 2024–2026 full-PPR per-game figures for QB12, QB24, RB30/31, WR42/43
and TE14 (QB24 about 13.8 a game vs the best remaining flex option about 10–11). Nothing else.

## 6. What A Change Would Mean

- **New lines change every value at the position** (more value above a lower line, less above a higher one), and with it
  the position-balance exchange rate (`DECISION-position-balance.md`).
- **Not a 2% accuracy test:** the lines define what value means, so there's nothing to predict.
- **Adopting new lines is Steve's call.** It would mean rebuilding values and re-checking the studies that depend on
  them.
