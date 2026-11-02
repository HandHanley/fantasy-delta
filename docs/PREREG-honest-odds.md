# PRE-REGISTRATION — Making "Players Like Him" Odds Honest

**Drafted:** 2 November 2026, before any result exists. **Status: LOCKED** by the commit that adds this file with `study/honest_odds_study.py` and `study/test_honest_odds.py` (2 Nov 2026, approved by Steve). The hash is recorded in the Project copy and `study/STUDIES.md`.
Locked by committing it to the repo as `docs/PREREG-honest-odds.md` with its two scripts, before the confirmatory run.

---

## Plain-English Summary (For Steve)

**The problem.** On 1 Nov, comparables value ("Players Like Him") predicted value well, but its odds were off. When it
said a veteran had a 24% chance of a starter season, it happened 20% of the time. Rookies went the other way: 21% said,
24% happened. Odds like that can't go on a card.

**Two suspects.**
1. **The league got bigger.** About 490 players a season saw the field in the 2000s; about 595 by 2020. There are still
   only 24 starter spots per position, so each player's chances shrank. Comparables from smaller, older leagues hit more
   often than a player can today.
2. **Rookies got better, faster.** DELTA's own research found it twice: a 5th-pick running back earned a real role 68% of
   the time in 2000–14 and 96% in 2015–23; QBs drafted 33rd–64th went from 5.2 to 12.2 points a game. Comparing a 2025
   rookie with 2005 rookies undersells him.

**The test.** Build two fixes, one per suspect, and check all three versions (as-is, Fix 1, Fix 2) on **players the odds
have never been graded on**. Whichever version gives honest odds there is the one a card could show.

**One change to the number itself.** The card would show "chance of a starter season in the **next three years**", not
five. Three years is how we get fresh players to test on (five-year results only exist up to 2020, and those are the ones
we already looked at). Three years is also a more useful number for a dynasty manager.

---

## 1. What This Tests, And What It Doesn't

**Tests:** which version of the comparables odds is honest on fresh data.

**Two numbers:** **P3**, the chance of at least one starter season (top 24 QB/RB/WR, top 12 TE) in the next three seasons;
**E3**, the expected number of starter seasons in the next three.

**Does not test or change:** the comparables value itself (1 Nov), the DELTA Score, projections, model value, buy/sell
calls, the market. **Nothing on the site changes.** Putting odds on a card needs Steve's approval after the result.

## 2. Prior Looks — Full Disclosure

- **1 Nov run (`docs/PREREG-comparables-value.md`, locked `c3f2428`).** We saw the five-year odds on 2013–2020 snapshots:
  middle bins too high (said 43%, happened 34%), veterans about 4 points high every year, incoming rookies slightly low,
  honest only at RB. **Both fixes below were chosen because of that pattern**, so that data cannot test them (lesson 6).
- **Era shift for rookies:** handoff §6 (rookie table refit; role-entry odds by era). Known before this draft.
- **League growth:** veteran snapshot counts per season, counted 1 Nov without outcomes (458 in 2001, 580 in 2020).
- **2 Nov, comps-vs-market draft:** built three-year outcomes for 2018–2022 snapshots inside its code, but **no odds were
  computed or graded** in that work, and the study stopped before any real result.

## 3. The Fresh Test Set

**Snapshots at the end of seasons `t` = 2021 and 2022**, every veteran and incoming rookie, built exactly as on 1 Nov
(per-season roster positions). Their three-year windows (2022–24, 2023–25) are complete and **no prediction for these
players has ever been graded.** Expected size: about 600 veterans and 80 rookies a season, about 1,350 rows.

Pool for each, by the time rule: snapshots from seasons ≤ `t − 3` (2001–2018 for 2021; 2001–2019 for 2022).

**Seen-data check (reported, decides nothing):** the same three versions on `t` = 2013–2020 with three-year outcomes,
labelled as data the fixes were designed from.

## 4. The Three Versions

All use the 1 Nov comparables exactly: same features, same weights, same 30 nearest, veterans with veterans, rookies
with rookies. Only how the 30 comparables' outcomes are **averaged** changes. Nothing is fitted to outcomes.

- **As-is.** P3 = share of the 30 who had a starter season in their next three; E3 = their average count.
- **Fix 1 — League Size.** Each comparable's result is scaled by how crowded his league was compared with today's:
  `× N(s, pos) / N(t, pos)`, where `N` = players at that position with at least one game that season (known at the
  time). A comparable from a season with 20% fewer players at his position counts 20% less. P3 capped at 100%.
- **Fix 2 — Recent Comparables Count More.** Same 30 comparables, but each is weighted by how recent he is: weight halves
  for every **8 seasons** between his season and the player's (`0.5^((t − s)/8)`). Eight is fixed, not tuned: across an
  18-season pool, the oldest comparables count about a quarter as much as the newest.
- **Both together** is reported only.

## 5. The Bar

**"Honest"** uses the 1 Nov rule unchanged (amendment A6 there): P3 binned in tenths, E3 binned by deciles; calibration
error vs a perfectly honest forecaster drawn from the same version's own comparables, 2,000 times; honest overall at the
95th percentile **and** at every position at the 99.375th.

**Accuracy guard.** A version only counts if its average squared miss on P3 (the Brier score) is no more than 1% worse
than As-is. Honest-but-vague odds (everyone 20%) shouldn't win.

**What goes on a card:**
1. If **As-is** is honest on fresh data: it is used. No fix needed. (Possible: three-year odds over a newer pool may already
   be fine.)
2. Otherwise, any fix that is honest and passes the guard; if both, the one with the lower Brier score.
3. If none is honest: no odds on cards. Comparables can still be shown as names and what they did.

## 6. Crash Tests, Before Lock

The fresh set is small (two seasons), so first prove it can tell honest odds from dishonest ones (lesson 10).

1. **Honest world.** Outcomes drawn from As-is's own comparables. As-is must be judged honest in **at least 80% of 200
   runs.** (Ten checks share the error rate, so it can't be 95%; this measures how often the check wrongly cries foul.)
2. **Dishonest world, the size we saw.** Outcomes drawn from As-is's probabilities with veterans scaled to 0.83 of the
   stated chance and rookies to 1.12 (the 1 Nov gaps: 20.2/24.2 and 23.7/21.2). The check must call As-is dishonest in
   **at least 80% of 200 runs.** If not, two fresh seasons are too few to see a problem that size, and that is reported
   before any real result.
3. **Leak checks (asserted):** pools ≤ `t − 3`; no player in his own pool; features and eligibility read nothing after `t`;
   `N(t, pos)` uses season `t` only.

## 7. How To Run This

1. Write `study/honest_odds_study.py` (reusing `comps_value_study.py` with roster positions and a three-year horizon) and
   `study/test_honest_odds.py` (§6).
2. Run the crash tests; record them in §9. If underpowered, stop and report.
3. Lock: commit this document and both scripts; record the hash.
4. Run once. Save `study/out/honest_odds_results.json`. Verdict to `study/STUDIES.md`. Report to Steve.

## 8. What Each Result Means

| Result | What A Card Could Show (Steve's OK Still Needed) |
|---|---|
| As-is honest | Three-year odds as they are |
| A fix honest, As-is not | Three-year odds from that fix |
| Nothing honest | No odds; comparables' names and what they did only |
| Underpowered (crash test 2) | Wait for the 2023 snapshot to close (after the 2026 season) and re-check |

## 9. Amendments

### Pre-lock (2 Nov 2026)

- **A1. How the honest forecaster draws E3.** For each player, pick one of his comparables by the version's weights,
  then keep each of that comparable's starter seasons with probability equal to his Fix 1 ratio (1 for As-is and Fix 2).
  Its average equals the stated E3 exactly. P3 is drawn as a plain yes/no at the stated chance.
- **A2. Fresh set, counted (no outcomes).** 1,359 rows: 1,200 veterans and 159 incoming rookies; QB 189, RB 370, WR 523,
  TE 277.
- **A3. What the league-size counts show (counted, no outcomes).** Players with at least one game, 2001 → 2022: QB 74 → 83,
  WR 169 → 226, TE 92 → 120, **RB 158 → 160** (and 115 in 2010). So the league grew at QB, WR and TE but not at RB, which
  fits RB being the one position that was already honest on 1 Nov. Fix 1 runs as written either way.

### Pre-lock crash-test results (2 Nov 2026, `study/out/honest_odds_crash.json`) — **POWERED**

| Synthetic World | Runs | Result | Bar |
|---|---|---|---|
| Honest odds | 200 | Called honest **85%** of the time | ≥ 80% |
| Odds wrong by the 1 Nov amount (veterans 0.835×, rookies 1.118×) | 200 | Caught **93.5%** of the time | ≥ 80% |

False alarms in the honest world were spread across checks (overall P3 12, overall E3 7, RB P3 6, others ≤ 3). The
dishonest world was mostly caught by the overall checks (P3 133 of 200, E3 154 of 200).

### Results (2 Nov 2026) — `study/out/honest_odds_results.json`

**Decision under the locked rule: Fix 2 (Recent Comparables Count More).** It is the only version judged honest on the
fresh 2021–2022 players, and it passes the accuracy guard.

| Version | Honest On Fresh Players? | Veterans: Said / Happened | Rookies: Said / Happened | Brier (lower is better) |
|---|---|---|---|---|
| As-is | No (overall P3, overall E3, WR P3) | 20.6% / 17.1% | 18.0% / 20.8% | 0.0802 |
| Fix 1, League Size | No; also fails the accuracy guard | 17.3% / 17.1% | 15.2% / 20.8% | 0.0814 |
| **Fix 2, Recent Count More** | **Yes, all ten checks** | 19.8% / 17.1% | 18.9% / 20.8% | **0.0797** |
| Both (reported only) | No (overall P3, overall E3) | 17.0% / 17.1% | 16.4% / 20.8% | 0.0809 |

Stated plainly:
- **Fix 2's pass is narrow.** Its overall P3 error was 0.027 against a limit of 0.029. Veterans still lean about 2.7 points
  high (19.8% said, 17.1% happened); on 1,359 fresh players that lean is within what an honest forecaster shows by chance.
  The crash test says this check catches a lean of the 1 Nov size (veterans at 0.835×) 93.5% of the time; Fix 2's lean is
  smaller (about 0.86×), so "honest" here means "no problem detectable at this sample size", not "perfect".
- **Fix 1 fixes veterans and breaks rookies.** Scaling for league size brings veterans to 17.3% vs 17.1%, but pushes rookies
  further below what happened. That fits the two-suspect picture: league growth explains the veterans, era change the rookies.
- **Seen data (2013–2020, three-year odds, designed-from, decides nothing):** As-is, Fix 1 and Fix 2 are all not honest
  there; Both is honest there. Fix 2 still leans high on veterans (21.7% vs 18.9%).
- **Not tested, found after the run:** league-size scaling for veterans only, plus recent-count-more for everyone, would
  likely beat all four. That is a new idea from seen results and needs fresh players: the 2023 snapshot's three-year window
  (2024–2026) closes after the 2026 season, in early 2027.
