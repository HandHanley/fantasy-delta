# PRE-REGISTRATION — Market Vs DELTA, Head To Head, By Position

**Drafted:** 8 November 2026. **Status: LOCKED 8 Nov 2026 (amendment A1: running backs decide).** Steve: "Sounds good let's do it" (8 Nov). Locks by
committing this document with `study/market_head_to_head.py` and its crash results, before the one real run.

---

## Plain-English Summary (For Steve)

**The question.** At running back and tight end (and the other positions), when the market and DELTA disagree about
who's better, who turns out right?

**How.** Each late summer from 2015 to 2023, take the dynasty market's draft order (Fantasy Football Calculator's 12-team
dynasty mock drafts) and DELTA's offseason value for the same players. Within each position, look at every pair of
players. Three seasons later, which one actually produced more? Score the market and DELTA on how often each had the
pair in the right order.

**What it settles.** If the market is clearly better at RB and TE, it knows something about how long those players stay
elite that DELTA's history-based matching doesn't, and DELTA should learn it. If DELTA is clearly better, those gaps are
DELTA's edge. If neither, they're two honest opinions.

## 1. Data

- **Market:** `data/fixtures/ffc-dynasty-adp-YYYY.json`, 2015–2023 (fetched 8 Nov by `scripts/fetch-ffc-rookie-adp.js
  --format dynasty`). 12-team mock drafts on FFC's site, late summer, **1QB** (the first QB goes around pick 28). FFC's
  API is free for commercial use and asks for "a link or mention of some kind" (About page). 1,534 QB/RB/WR/TE rows.
- **DELTA:** the adopted offseason Own Value Scale (`study/ovs_era.py`: era-adjusted matching, three seasons ahead, pool
  `≤ t − 3`), snapshot `t = Y − 1`; incoming rookies use their draft-day snapshot. Code unchanged.
- **Truth:** FV3 over seasons Y, Y + 1, Y + 2 (12-team superflex lines, half PPR + TE premium), as in the Own Value Scale.
- **Matching names:** FFC's name + position against each snapshot player's nflverse names (display, first, football and
  common first names), one hit required. **1,485 matched**; 6 ambiguous and 43 unmatched dropped. The unmatched are
  almost all players with no game in the season before (Andrew Luck 2018, Josh Gordon 2016–17): DELTA has no snapshot
  for them. That rule uses only what was known at the time.

## 2. Why Within Position

The market is 1QB and DELTA's value is superflex, so comparing a QB with a receiver would mix formats. Within a
position, the order doesn't depend on that: RB, WR and TE lines are identical in both, and a QB's order among QBs barely
moves. It is also the question Steve asked.

## 3. The Measure And The Rule

- **Pairs:** every two players of the same position in the same year whose three-season outcomes differ (RB 11,361;
  WR 16,606; QB 2,465; TE 1,469).
- **Score:** the share of pairs each method ordered right (market: earlier pick; DELTA: higher value; a tie counts half).
- **Range:** 4,000 resamples of players (a pair is weighted by how often both of its players are drawn), seed 20261108,
  **98.75%** (four positions decide).
- **Verdict per position:** range above zero → **market better**; below zero → **DELTA better**; otherwise **no clear
  winner**.

## 4. What Each Verdict Allows (Steve's OK Needed)

| Verdict At RB And TE | Next Step |
|---|---|
| Market better | Find what the market sees (persistence of elite RB/TE seasons) as its own pre-registered study |
| DELTA better | The RB/TE gaps stand as DELTA's calls |
| No clear winner | Two honest opinions; DELTA's stands, flagged where they differ |

The DELTA Score is untouched, and no market number enters DELTA's value from this study.

## 5. Reported, Deciding Nothing

All positions together; rookies-only and veterans-only pairs; each year.

## 6. Prior Looks

- DELTA's own predictions and their accuracy against FV3 on these seasons are known (`PREREG-ovs-era.md`).
- No market order has ever been compared with an outcome in any DELTA study. The fetched files were read only for their
  size, dates and settings (8 Nov).

## 7. Crash Tests, Before Lock

Synthetic outcomes from each method's standing within its year and position (standardised rank), plus noise:
`outcome = w × market standing + (1 − w) × DELTA standing + noise`.
- **Tie (w = 0.5):** the verdict must be "no clear winner" in **≥ 95% of 100 runs** at every position.
- **Market planted (w = 0.75)** and **DELTA planted (w = 0.25):** the right verdict in **≥ 80% of 100 runs at RB and
  TE** (TE has the fewest pairs); other positions reported.

500 resamples per crash run (4,000 in the real run).

## 8. Limits

- Mock drafts, not real trades; 1QB, not superflex.
- Late-summer market vs DELTA's offseason value (built from the season before): the market has seen the offseason's
  news (camp, depth charts) that DELTA can't.
- Nine years; TE has the fewest pairs.

## 9. Amendments

**Crash tests (8 Nov, `study/out/market_h2h_crash.json`, 100 runs, 500 resamples): FAIL at tight end.**

| Position | Tie: "No Clear Winner" (Bar 95) | Market Planted: Right Verdict (Bar 80) | DELTA Planted: Right Verdict (Bar 80) |
|---|---|---|---|
| RB | 100 | **85** | **81** |
| WR | 100 | 78 | 79 |
| QB | 99 | 37 | 42 |
| TE | 99 | **33** | **29** |
| All together | 100 | 100 | 100 |

Never a false winner. RB has the power to decide; TE (179 players, 1,469 pairs) doesn't. Per §7, this goes to Steve
before any real result; nothing has been run.

**A1 (8 Nov, Steve: "Go" to option A): only running backs decide.** RB's verdict uses the 98.75% range the crash test
passed with. WR, QB, TE and all positions together are reported with their ranges as **leanings, not verdicts**; the TE
result especially cannot settle anything (right verdict in about 30 of 100 planted runs). The table in §4 now reads
"verdict at RB". Decided before any real result.

## 10. Results (8 Nov 2026, Run Once)

`study/out/market_h2h_results.json`. **Verdict at running back (deciding): the market is better.**

| Position | Pairs | Market Ordered Right | DELTA Ordered Right | Gap | 98.75% Range | Reading |
|---|---|---|---|---|---|---|
| **RB (decides)** | 11,361 | **73.3%** | 69.2% | **+4.1** | +0.4 to +7.9 | **Market better** |
| WR | 16,606 | 72.1% | 71.2% | +0.9 | −2.3 to +3.9 | Leaning market, no verdict |
| QB | 2,465 | 69.2% | 65.0% | +4.2 | −3.0 to +11.4 | Leaning market, no verdict |
| TE | 1,469 | 68.1% | 64.7% | +3.4 | −4.8 to +11.1 | Leaning market, no verdict (underpowered) |
| All together | 31,901 | 72.1% | 69.7% | +2.4 | +0.3 to +4.6 | Reported |

**Reported, deciding nothing.** Veterans-only pairs: market 73.5%, DELTA 71.0%. Rookies-only pairs: market 67.4%, DELTA
64.8%. By year, the market was ahead in 7 of 9 (2015, 2017, 2018, 2019, 2021, 2022, 2023), about even in 2016 and 2020.

**How to read it.** The market's late-summer order knew things DELTA's offseason value can't: free agency, the NFL
draft, depth charts, camp (§8). Running backs' roles change most in exactly that window, so part or all of the market's
edge may be offseason news, not a better read of how long elite players last. Either way, at running back the market's
order has been the better guide to the next three seasons, by about 4 pairs in 100.

**Next (each its own pre-registration, Steve's OK):** what the market sees that DELTA doesn't, starting with the
"true peers for elite players" idea (fewer, closer matches for rare players) and an offseason-news signal DELTA could
measure itself (role and team changes between seasons).
