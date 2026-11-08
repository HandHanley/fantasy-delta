# PRE-REGISTRATION — Own Value Scale: Offseason Changes

**Drafted:** 8 November 2026. **Status: LOCKED 8 Nov 2026 (amendment A1).** Steve: "Offseason changes. Draft it and run it."
Locks by committing this document with `study/ovs_offseason.py` and its crash results; runs only if they pass.

Follows `docs/PREREG-market-head-to-head.md` (8 Nov): at running back the market's late-summer order beat DELTA's
offseason value (73.3% vs 69.2% of pairs right), plausibly because the market had seen the offseason's news.

---

## Plain-English Summary (For Steve)

**The idea.** Measure the offseason news ourselves, from facts: who's on his team when the season starts, and what his
team spent on his position in the draft. Then compare each veteran with past players who were in a similar spot.

**Two facts per veteran, for the season ahead:**
- **His share of his club's production at his position:** last season's points by everyone at his position on his club
  (him included). A big signing pushes it down; a departure pushes it up; a player who moved is measured against his
  new teammates.
- **Early draft picks at his position:** his club's round 1–2 picks at his position that spring.

**The test.** Do veteran running backs' values predict their next three seasons at least 2% better, without hurting
anyone else?

## 1. Data

- **Rosters:** nflverse weekly rosters 2002–2026 (`roster_weekly_YYYY.csv`). A player's club for season Y = his first
  listing **on the club** (active, injured reserve, inactive, suspended, PUP, non-football injury, exempt, reserve) in
  the season's first five weeks (each club's first game is its week 1; 2017's Irma postponement handled). Five weeks so
  a four-game suspension still counts (early files omit suspended players until they return: Jimmy Smith 2003, week 5).
  Cut, free-agent and practice-squad listings don't count. No club → share 0, picks 0 (3,029 of 12,558 veteran
  snapshots, mostly fringe players and retirements: 43% of players under 50 points, 4% over 150).
- **Draft:** nflverse `draft_picks.csv`, picks 1–64. Team codes mapped to one code per club across both files.
- **Points:** the season file (half PPR + TE premium), the player's position that season.
- **Checked before any outcome:** McCaffrey 2019 share 0.96 (CAR RBs), Kelce 2022 0.74, Jonathan Taylor 2021 0.77,
  Davante Adams 2021 0.52.

## 2. The Change, And Only The Change

The adopted offseason value (`study/ovs_era.py`: era-adjusted matching, three seasons ahead, pool `≤ t − 3`, test
seasons 2013–2022) with two veteran matching features added: **share (weight 1.5)** and **picks (weight 1.0)**.
Production 3.0, age 2.0, draft slot (Version A), career year 1.0, games 1.0, 30 matches, Fix 2 weights: unchanged.
Rookie (draft-day) matching unchanged (asserted).

## 3. The Questions

- **Decides:** veteran running backs (the position where the market won): RMSE on FV3 at least **2% better**, paired
  permutation p < 0.05 (a player's rows together, 10,000 shuffles); **and** all rows no more than 0.5% worse; **and**
  close synthetic trades no more than 1.0 point worse.
- **Decision:** passes → the offseason value uses the two features (Steve's OK). Fails → it stays as adopted.

## 4. Reported, Deciding Nothing

Each position's change; the market head-to-head at RB rerun with the new value, to see whether the gap closes.

## 5. Prior Looks

- The adopted value's results on these seasons are known (era study: all rows 51.5 RMSE on FV3).
- The market head-to-head result is known (RB: market 73.3%, DELTA 69.2%).
- No offseason feature has been compared with any outcome; only the spot checks in §1.

## 6. Crash Tests, Before Lock

The era study's worlds with this rule: noise (outcomes shuffled within position and season) passes in at most 1 of 20;
planted w = 0.75 passes in ≥ 80% of 200; w = 0.6 reported. 1,000 permutations per crash run.

## 7. Limits

- First-five-weeks club, not the August roster the market saw; cut-down day moves are included, a few early-season
  signings too.
- Share uses last season's points, so it can't see a new player's role beyond what he did elsewhere, or a coach's plan.
- Picks count early-round investment, not who wins the job.

## 8. Not Licensed Here

The DELTA Score, the site's model value, buy/sell calls. Nothing on the site changes.

## 9. Amendments

**Crash tests (8 Nov, `study/out/ovs_offseason_crash.json`): narrow FAIL.** Noise world 0 of 20 (pass). Planted w = 0.75:
**154 of 200 (77%, bar 80%)**, typical RB lift 2.7%. w = 0.6: 6 of 50.

**One alternative checked, not adopted:** deciding on all 5,693 veteran rows instead of veteran RBs: planted w = 0.75
passed 110 of 200 (55%), noise 0 of 20. Worse, because the features move running backs most.

Per §6 this goes to Steve before any real result. Nothing has been run.

**A1 (8 Nov, Steve: "Run it"), after hearing the crash result:** run under the RB rule as written, knowing the test
catches a real 2.7%-sized gain about 77 times in 100. Read the result this way, decided now: **a pass counts** (the
noise world never passed); **a fail is inconclusive**, not evidence the features don't help, and the test is repeated
when the 2023 class's window closes (early 2027).

## 10. Results (8 Nov 2026, Run Once)

`study/out/ovs_offseason_results.json`. **Passed: the offseason value uses the two features** (Steve's OK given before
the run).

| Question | With Offseason Changes | Without | Result |
|---|---|---|---|
| Veteran running backs (1,624 rows) | — | — | **2.6% better, p = 0.044** (bar 2%, p < 0.05) |
| All 6,484 rows | — | — | 1.7% better (guard: no more than 0.5% worse) |
| Close synthetic trades called right (23,385) | 56.8% | 53.1% | **+3.7 points, p = 0.0005** (guard: no more than 1 worse) |

Every position improved (all rows of each): QB 1.6%, RB 2.0%, WR 1.6%, TE 1.2%. The deciding p-value is close to the
bar (0.044 against 0.05); stated plainly, not rounded away.

**Reported: the market head-to-head rerun with the new value** (`study/out/ovs_offseason_h2h_reported.json`).

| Position | Market Ordered Right | DELTA Before | DELTA Now | Verdict Now |
|---|---|---|---|---|
| RB | 73.3% | 69.2% | **70.1%** | No clear winner (was: market better) |
| WR | 72.1% | 71.2% | 71.3% | No clear winner |
| QB | 69.2% | 65.0% | 66.2% | No clear winner |
| TE | 68.1% | 64.7% | 65.9% | No clear winner |

The RB gap shrank from 4.1 to 3.2 points and is no longer clearly in the market's favour; the market still leads at
every position.

**Live use:** the offseason value reads each veteran's current club and that spring's draft as they happen (free agency
in March, the draft in April); from week 5 the in-season value takes over.
