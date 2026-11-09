# PRE-REGISTRATION — Own Value Scale: Points Per Available Game Instead Of A Games Count

**Drafted:** 9 November 2026. **Status: LOCKED by the commit that adds this file with `study/ovs_available_ppg.py`,
before the one run.** Steve: "On suspensions, I agree - let's leave them out. I do think the PPG trust is a decent
issue, I'd be curious to see what this test does and to see if it comes out better or worse - let's run it. My
suspicion is that we'll still need some sort of PPG metric in there."

---

## Plain-English Summary (For Steve)

**Today (in-season):**

- Production is points per game **played**.
- A separate "games played" number helps find similar past players. Weeks out hurt are credited as games
  (`DECISION-no-games-in-matching.md` §5).

**The change:**

- Production becomes points per game **available**. Weeks he was healthy and on the game-day roster but didn't play
  count as 0-point games. Weeks out hurt, suspended, exempt, on bye or on no club don't count at all.
- The separate games number is deleted. Nobody gets credit for games he didn't play, and injuries still cost nothing.

**The test:** at week 9, 2013–2022, is it no more than 1% worse at predicting the next three seasons?

The bar is "no worse" because this is a cleaner design, not a bid for accuracy. That's the same bar as dropping draft
slot on 2 November.

## 1. The Change, And Only The Change

- **Available weeks** (`study/injury_weeks.py`, `available_weeks`):
  - every week he played, plus weeks on a club's game-day roster (weekly status ACT or INA; any listing in the older
    2002–2015 files) when his club played and he did not;
  - minus weeks he was hurt. Hurt means the §5 rule, plus any injury-report listing (Out, Doubtful or Questionable) in
    a week he did not play. This closes the gap where Caleb Williams's 2026 week 5 (Questionable, then inactive) was
    missed.
- **Production:** the same era-adjusted 3/2/1 blend (this season through week 9, then the two seasons before). Each
  season's points are divided by **available** games instead of games played. A season enters the blend when he had at
  least one available game.
- **The games feature:** weight 0.
- **Unchanged:** outcomes (FV3), the 30 matches, the pool, recency weighting, everything else.
- **Rows:** the same week-9 rows as §5.

**Checked by hand (through week 9, played → available):**

| Player | Season | Played | Available | Why |
|---|---|---|---|---|
| Caleb Williams | 2026 | 5 | 5 | Weeks 3–5 out hurt, all left out |
| Josh Jacobs | 2026 | 2 | 2 | Exempt list, left out |
| Brock Purdy | 2026 | 7 | 7 | |
| Dez Bryant | 2015 | 3 | 3 | Foot, left out |
| Le'Veon Bell | 2015 | 6 | 6 | Suspension, left out |
| Tyrod Taylor | 2026 | 1 | 8 | Backup |
| Jarrett Stidham | 2026 | 0 | 8 | Backup |
| Matt Cassel | 2015 | 3 | 8 | Backup most of the way |

## 2. The Questions

- **Decides:** typical miss (RMSE, FV3) over all week-9 rows, new vs today's in-season value. It must be **no more than
  1% worse**; **and** close synthetic trades no more than 1.0 point worse.
- **Decision:** passes → in-season uses points per available game and no games number (Steve's OK). Fails → today's
  injury-neutral games stays.
- **Reported, deciding nothing (Steve's question):**
  - The new production **plus** the injury-neutral games number. Does a "how many games is this based on" measure still
    help once production is per available game?
  - Players with 2+ weeks out hurt, and players with 5 or fewer games never hurt: what they produced ÷ each version's
    value.
  - By position. Paired permutation p.

## 3. Prior Looks

- Today's in-season value's results are known (§4 and §5 of the decision doc).
- No outcome has been compared with any per-available-game value.

## 4. Limits

- The older files (2002–2015) don't separate short game-day injuries from healthy scratches before 2009 (no injury
  reports). Those weeks count as 0-point available games.
- Weeks on no club don't count, because the older files can't show them. Players out of work show up through earlier
  seasons, as now.
- Starter levels (era scaling) are unchanged: per game played among the top starters.

## 5. Not Licensed Here

The DELTA Score, the site's model value, buy/sell calls. Nothing on the site changes.

## 6. Results (9 Nov 2026, Run Once)

`study/out/ovs_available_ppg_results.json`. The lock commit was rebased onto the nightly data update before the push (no
study files touched); the locked commit is `8baa510`. Equivalence check: with available = played, the new production
code reproduced today's production on every row. Production changed on 5,109 of the 6,808 rows.

**Decision: passes. In-season uses points per available game, with no games number.**

| Week 9 (6,808 rows) | Typical Miss | Close Trades Called Right |
|---|---|---|
| Per available game vs today | 48.28 vs 48.07 (**0.4% worse**, bar 1%) | 55.7% vs 54.3% (**1.3 points better**) |
| Per available game + games number vs today (reported) | 48.04 vs 48.07 (0.1% better) | 56.7% vs 54.2% (2.5 points better) |
| Per available game + games number vs per available game alone (reported) | 0.5% better (p = 0.03) | 1.4 points better |

By position, per available game vs today: QB −0.1%, RB 0.0%, WR −1.1%, TE −0.9%.

**What each group produced, as a share of its value:**

| Group | Today | Per Available Game | Plus Games Number |
|---|---|---|---|
| 2+ weeks out hurt (986 rows) | 69% | 74% | 69% |
| 5 or fewer games, never hurt (3,176 rows) | 55% | 39% | 51% |

**What it means.**

- **Accuracy:** points per available game is about as accurate as today, and calls close trades slightly better.
- **Steve's hunch was partly right:** a "how many games is this based on" number still adds a little (0.5%, real but
  small). But the games number tested here is the credited-games version, the patch this change replaces.
- **Injured players:** now valued a bit closer to what they went on to do.
- **Low-games players who were never hurt:** valued further above what they went on to do.

**Today's page (week 9, full PPR, 12-team superflex; injury credit → per available game):**

| Player | Injury Credit | Per Available Game | Why |
|---|---|---|---|
| Malik Willis | 43 | **138** | 2025: played 4 of 17 active weeks as a backup |
| Drake Maye | 2 | 6 | |
| Puka Nacua | 6 | 2 | |
| Brock Purdy | 7 | 7 | |
| Caleb Williams | 12 | 12 | |
| Goff vs McBride | 22 vs 24 | 17 vs 23 | |
| Baker Mayfield | 77 | 85 | |
| Josh Jacobs | 103 | 57 | Exempt weeks left out |
| Cam Skattebo | 49 | 111 | One healthy week not played; no games number |
| Fernando Mendoza | 69 | 130 | Rookie, active all 8 weeks, played 1 |

Position balance (average rank among all valued players, market in brackets): QB 56 (60), RB 101 (76), WR 84 (79), TE
119 (90). Agreement with FantasyCalc: 0.81 (unchanged).

**Open question for Steve:** should a rookie sitting behind a starter (Mendoza) count his healthy inactive weeks as
zeros, like a benched veteran?

## 7. Amendment: Rookie QBs Who Sit (9 Nov 2026, Before Its Run)

Steve: "what about no, but only for QBs? … rookie QBs are usually taken with the expectation of sitting … I don't think
it should work that way for RBs, WRs and TEs, as those positions earn reps more than a planned QB."

**The rule (Steve's design call, not decided by a test):**

- A QB in his first NFL season (no games in any earlier season) counts only the games he played that season. His
  healthy weeks not played don't count.
- The same rule applies to the history the matches come from, so past sitting rookie QBs are treated the same way.
- Every other player and season is unchanged from §1.

**Measured once, deciding nothing (`study/ovs_rookie_qb.py`):**

- Week 9, 2013–2022, all rows and the first-year QB rows: typical miss with and without the rule.
- First-year QBs: what they produced ÷ each version's value.
- Today's page rebuilt (Fernando Mendoza and the other first-year QBs).

### Results (9 Nov 2026, Run Once)

`study/out/ovs_rookie_qb_results.json`. 119 first-year QB rows changed across all seasons (82 in the 2013–2022 test
rows, 61 of them changed). No other row changed (asserted).

| Week 9 | Without The Rule | With The Rule |
|---|---|---|
| All rows: typical miss | 48.28 | 48.56 (0.6% worse) |
| First-year QBs: typical miss | 101.5 | 111.1 (9.5% worse) |
| First-year QBs: produced ÷ value | **137%** | **101%** |
| Close trades called right | 56.5% | 56.1% |

**What it means.**

- **Without the rule, sitting rookie QBs were undervalued as a group:** they went on to produce about a third more than
  their value.
- **With the rule, the group is valued about right on average.**
- **But each guess misses by more.** A sitting rookie's points per game now rests on the one or two games he did play.
  That is Steve's "how many games is this based on" concern showing up exactly where expected.

**Today's page:** Fernando Mendoza 130 → 110 (market 43). Other QBs shift a few places through their matches, e.g. Maye
6 → 11 and Purdy 7 → 6.

## 8. Amendment: QB Games Follow The Start Profile Rule (9 Nov 2026, Before Its Run)

Steve: "can you look at how we calculate starts for QBs in the Start Profile? I think we need to merge that here …
That helps us filter out the 'Mendoza game in at the end of the game when they were getting blown out'."

**The rule (Steve's design call, the engine's `qbSpCounts`, measured and not decided by a test).** Code:
`study/qb_games.py`.

- **A QB week is a game** when he took part (a pass, carry, target or catch, or any offensive snap) and any of these
  holds:
  - **He started it:** the nflverse schedules name him, by player ID, back to 1999. An injury exit still counts.
  - **He played 75%+ of the snaps:** nflverse snap counts, 2012 onward.
  - **Before 2012, with no snap counts:** he threw his team's most passes that week, 10 or more.
- **The engine's correction is kept:** a listed start doesn't count when another QB on the team played 95%+ of the
  snaps.
- **Any other week he took part in is a cameo:** mop-up, kneel-downs, a planned rest. Its points and the week itself
  are left out, for every QB.
- **Everything else in §1 and §7 is unchanged:**
  - A dressed veteran backup's week with no game is a 0-point available week.
  - A first-year QB counts only his games.
- **A first-year QB with no game yet** has no production to match on. He is valued as an incoming rookie (draft slot and
  age, matched with past incoming rookies) and is left out of everyone else's matches.

**Checked by hand before any outcome was read:**

| Case | Games | Cameos |
|---|---|---|
| Fernando Mendoza 2026 | none | week 5 (blowout) |
| Josh Allen 2024 / 2025 | 16 / 16 | week 18 rest, both years |
| Drake Maye 2024, C.J. Stroud 2024 | 11, 16 | week 18 rest (Maye also week 3 relief) |
| Joe Flacco 2024 | 7 | week 8 (listed; Richardson played 98%) |
| Jayden Daniels 2024 | 17 (weeks 9–13 the schedule wrongly listed Mariota) | none |

Across 1999–2026 there are 14,460 QB games (14,117 starts, 102 by 75% of snaps, 241 by most passes before 2012) and
2,705 cameos.

**Measured once, deciding nothing (`study/ovs_qb_starts.py`):**

- Week 9, 2013–2022: typical miss and close trades vs the value as of §7.
- QB rows, and first-year QB rows: typical miss, and produced ÷ value.
- How many rows switch to incoming-rookie values.
- Today's page.

**§8 note A (before any outcome was compared).** The first run stopped on its own safety check (no non-QB row may
change): 5 rows of position-switchers changed (Taysom Hill and Feleipe Franks as TEs, Joe Webb and B.J. Daniels as
WRs). The rule now applies only in seasons the player is valued as a QB (season file position). No rule changed.

**§8 note B (before any outcome was compared).** Note A was not the cause. The 5 rows are TE/WR rows whose production
blends earlier QB seasons (Taysom Hill 2022 blends his 2020–2021 QB seasons). The rule correctly applies to those
seasons. The check now asserts that every changed non-QB row has a QB season in its blend, and lists them.

**§8 note C (before any outcome was compared).** The next check stopped the run: 4 veteran QB rows had no production left,
because their only action was cameos (Tee Martin, Dameyune Craig and Mark Rypien in 2002, Tommy Stevens in 2021). A
veteran whose only action is cameos produced nothing, so his production is 0. Only first-year QBs take incoming-rookie
values.
