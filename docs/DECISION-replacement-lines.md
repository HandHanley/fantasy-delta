# DECISION — Where Should The Lines Be? (12-Team Superflex)

**Drafted:** 12 November 2026, before any allocation was run. **Status: MEASURED 12 Nov 2026; the decision is Steve's (§7).** Steve, 12
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

## 7. Results (12 November 2026)

`study/replacement_lines.py`, `study/out/replacement_lines_results.json`. A hand check of 2025 (DELTA lineup, half
PPR + TE premium) reproduced the code's counts exactly: QB 24, RB 34, WR 41, TE 21. The superflex spot went to a QB on
all 12 teams (Dart, Darnold, Love … Geno Smith). The flex spots went RB 10, TE 9, WR 5.

**Starters per position, DELTA's lineup (average per season):**

| Scoring, Method, Seasons | QB | RB | WR | TE |
|---|---|---|---|---|
| Today's lines | 24 | 30 | 42 | 14 |
| Half PPR + TE premium, season totals, 2021–2025 (decides) | **24.0** | **34.2** | **44.0** | **17.8** |
| Half PPR + TE premium, season totals, 2002–2025 | 23.8 | 34.7 | 45.3 | 16.1 |
| Half PPR + TE premium, week by week, 2021–2025 | 24.0 | 33.1 | 45.3 | 17.7 |
| Full PPR, season totals, 2021–2025 | 24.0 | 34.0 | 48.4 | 13.6 |
| Full PPR, week by week, 2021–2025 | 24.0 | 32.6 | 49.4 | 14.1 |

**2-WR lineup (reported), half PPR + TE premium, 2021–2025:** QB 24.0, RB 31.4, WR 38.6, TE 14.0.

**The lines in points (half PPR + TE premium, 2021–2025, season totals):**

- **QB:** the last starter scored 171.9, against 163.4 for the best QB left out. The best RB, WR or TE left out scored
  about 121–122, so a QB always takes the superflex spot.
- **RB, WR and TE:** the last starters scored 124–127.

**What it means.**

- **QB24 is right.** In every scoring and method, 24 QBs start, because the superflex spot always goes to a QB.
- **The other lines are too shallow.** Today's lines fill only 14 of the 24 flex spots. Measured, all 24 fill, so more
  RBs, WRs and TEs start than the lines assume.
- **Scoring decides the TE line.** With the TE premium, 18 TEs start; in full PPR without it, about 14.
- **Share of all value above the line (half PPR + TE premium, 2021–2025 average):**

| Position | Today's Lines | Measured Lines |
|---|---|---|
| QB | 32.1% | 28.1% |
| RB | 27.3% | 30.9% |
| WR | 32.4% | 30.7% |
| TE | 8.1% | 10.3% |

The top five TEs' points above the line rise about 21% (84 → 101 a season); the top five RBs' about 12%.

**Options for Steve:**

1. Adopt the measured lines per scoring: half PPR + TE premium QB24 / RB34 / WR44 / TE18; full PPR QB24 / RB34 / WR48 /
   TE14.
2. Keep today's lines.

Adopting means rebuilding the values on the new lines. Earlier studies were judged on the old lines; their conclusions
compare two versions on the same line, so they're unlikely to flip, but the values themselves move.

## 8. Adopted (12 November 2026)

Steve: "I like the updated weights and measurements, and I think we should lock it in and see an updated top 150."

- **Lines:** half PPR + TE premium QB24 / RB34 / WR44 / TE18 (`comps_value_study.REPL_N_ADOPTED`); full PPR QB24 /
  RB34 / WR48 / TE14 (`REPL_N_FULL_ADOPTED`). `REPL_N` keeps the old lines so every locked study reproduces; new builds
  and new studies use the adopted ones.
- **Not run against his own league,** by Steve's choice ("I don't want to influence the data").
- **Top 150 dashboard rebuilt** (`top150_v6.csv`, full PPR, Contract Security on; `study/top150_v6_values.py` and
  `top150_v6_rank.py`).
  - **Check:** the old lines reproduce the 10 Nov values exactly (all 146 valued rows). Ranks among site players
    differ by at most 3, because the site list matched 371 players instead of 374.
  - **"Lines Move"** compares old and new lines on the same rebuild.
- **Average move in the top 150:** QB −6.3 spots, RB +3.7, WR +4.7, TE −9.4. Examples:
  - Allen 2 → 3, Purdy 4 → 6, Bowers 36 → 40, McBride 21 → 23;
  - Bucky Irving 20 → 15, Cooper 47 → 43, Jefferson 80 → 75, Watson 58 → 64.
