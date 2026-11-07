# PRE-REGISTRATION (DRAFT, NOT LOCKED) — Vegas Team Context In DELTA's Own Value Scale

**Drafted:** 7 November 2026, before any result exists. Steve said go (7 Nov). **NOT LOCKED: the crash test showed the
study can't clear its bar (§11), so it was not run.** No real outcome was compared with any prediction.

---

## Plain-English Summary (For Steve)

**The idea.** Las Vegas sets a point spread and an over/under for every NFL game. Together they say how many points each
team is expected to score. That's the betting market's view of an offense: its quarterback, its line, its play-caller,
its injuries. DELTA's Own Value Scale (OVS) can't see any of that. This tests whether knowing "Vegas expected his offense
to score 27 a game" (or 17) makes OVS better at predicting what players go on to score, and at calling trades.

**The data is free and goes back to 1999.** It's nflverse's schedule file, which DELTA already uses.

**What you get back.** A yes or no on players and on trades, the same two questions OVS passed.

---

## 1. Where The Lines Come From (Checked 7 Nov, No Outcomes Looked At)

- **File:** `nflverse/nfldata`, `data/games.csv`, the same file `nflreadr::load_schedules()` reads. 7,548 games.
- **Coverage, regular season:**
  - spread and over/under on 100% of games from 1999 to 2025;
  - moneylines from about 2006;
  - 2026 lines through week 10 so far. Lines appear about a week before each game.
- **What they are:** closing lines. The repo doesn't say which sportsbook; nflverse's documentation names
  Pro-Football-Reference as the source for the total.
- **Sense check:**
  - implied home points (over/under ÷ 2 + spread ÷ 2) average 22.8, against 23.2 actually scored;
  - correlation with points actually scored is 0.38 for home teams and 0.39 for away teams;
  - the sign convention is confirmed.
- **Rights:**
  - The repo carries no licence file. DELTA already relies on nflverse throughout, with credit.
  - The lines themselves are facts (Feist v. Rural, 1991), and DELTA gets them secondhand, as it does the contracts.
  - Sports-Reference's own terms bind people who take data from its site. DELTA never does.
  - Only DELTA's derived value would be shown, never the lines.

## 2. What This Tests, And What It Doesn't

**Tests:** whether a team-context adjustment from Vegas lines (§5) makes OVS predict the next five seasons (FV5) better,
and call trades better.

**Does not touch:**
- the DELTA Score (production only, untouched);
- projections, model value, buy/sell calls, the accuracy ledger.

No FantasyCalc data. Nothing on the site changes.

## 3. Prior Looks — Full Disclosure

- OVS's own results on these test seasons are known (`claude/PREREG-own-value-scale.md`, locked `63c80df`). OVS beat B2
  by 6.2% on players and 12.4 points on trades.
- No Vegas line has ever been compared with a player outcome in any DELTA study. The only look at the lines file is the
  sense check in §1, which used team scores, not players.

## 4. Data, Snapshots, Outcome

Exactly as the Own Value Scale study:
- the same snapshots (veterans at the end of season `t`, incoming rookies), positions, half PPR + TE premium;
- the same FV5 outcome;
- test seasons `t` = 2013–2020, pool for each `t` = 2001 to `t − 5`.

OVS predictions are produced by the locked OVS code, unchanged (asserted row for row).

## 5. The Ingredient And How It's Used

**Team implied points.** For each regular-season game:
- home = over/under ÷ 2 + spread ÷ 2;
- away = over/under ÷ 2 − spread ÷ 2.

**Two versions:**

| Version | Ingredient | When It's Known | Role |
|---|---|---|---|
| **A, season-end (deciding)** | His season-`t` team's average implied points across season `t` (closing lines) | End of season `t`, so all offseason, when most dynasty trades happen | Decides |
| **B, Week 1 (reported only)** | His Week-1 team's implied points in Week 1 of season `t+1` (weekly rosters) | Only the week before Week 1 | Reported |

- Each value is divided by that season's league average, so "1.10" means Vegas expected his offense to score 10% more
  than average.
- Incoming rookies use the team that drafted them. Version A uses that team's season-`t` lines.
- If a player has no team, the value is 1.00. That case is counted.

**The adjustment:** OVS × (team ratio)^β. **β** is how strongly team context moves value. It is fitted for each test
season `t` by position, using only earlier seasons (see A1).
- **Time-safe:** the fit never sees a test season or anything after it.
- **Limits:** β is capped between 0 and 3.

**Why this shape.** A multiplier keeps zero at zero (a flop stays a flop). β = 0 means "lines add nothing", which is
the null.

## 6. The Questions (Same Bars As OVS)

- **Q1, players:** is OVS-Vegas's RMSE on FV5 at least **2% smaller** than OVS's?
  - Paired permutation test, 10,000 shuffles, all of a player's snapshots swapped together, one-sided.
  - Passes at **p < 0.025**.
- **Q2, trades:** on trade sets rebuilt with the OVS study's rules and seed, does OVS-Vegas call at least **2.0 points
  more** right than OVS?
  - Same permutation test, **p < 0.025**.

**Decision:** both pass, Version A can join OVS (Steve's OK). Either fails, OVS stays as it is.

**Reported only:** Version B; next season alone (FV1); by position; players who changed teams; the fitted β values.

## 7. Crash Tests (Before Lock)

1. **Noise:** team ratios handed to the wrong teams within each season, so the lines mean nothing. It may pass Q1 or Q2
   in at most 1 of 20 runs.
2. **Planted:** truth = OVS × (team ratio)^β₀ + leftover error around OVS (shuffled within position). β₀ is set in A2.
   It must pass both in at least 80% of 200 runs. If not, the study is too small to see an effect that size, and Steve
   hears that first.
3. **Leak checks, asserted in code:**
   - β never fitted on a season after `t − 5`;
   - Version A reads no line after season `t`;
   - OVS predictions match the locked OVS output row for row.

## 8. What Each Result Would Have Allowed

| Result | Allows (Steve's OK Still Needed) |
|---|---|
| Q1 and Q2 pass | Team context from Vegas lines joins OVS |
| Q1 passes, Q2 doesn't | Not used in trades. Reported |
| Neither | Documented null. Player props would be the next idea |

## 9. Honest Expectations, Stated Before Running

Team context is real, but some of it is already inside OVS: a player on a great offense already scored well last
season. Over five seasons, teams change, coordinators change and players move. So the 2% bar on FV5 may be out of reach
even if the lines help next season.

## 10. Amendments (Before Lock, Before Any Result)

- **A1. β fitted by least squares in value, not log value.** Most five-year values are zero, and log(0) doesn't exist.
  β is searched from 0 to 3 in steps of 0.01 on pool rows from 2006 (the first season with an OVS prediction) to
  `t − 5`.
- **A2. The planted strength is set by hand, not fitted.** The draft set β₀ to "the median β the fit finds on pool
  seasons". That would mean reading the real relationship before lock, so it was dropped. β₀ = 1.0 now decides: value
  rises one-for-one with team implied points, a strong effect. β₀ = 0.5 is reported. OVS is held at its real
  predictions, so the crash test asks whether the β fit and the two questions can find a planted team effect.
- **A3. Data counts.**
  - Version A team found for all but 8 of 5,125 test snapshots.
  - Version B (week-1 roster) found for all but 712.
  - Team ratios ranged from 0.68 to 1.47 of league average.

## 11. Crash Result (7 Nov 2026): FAILED, So Not Locked And Not Run

`study/out/vegas_context_crash.json`. Reduced run: 5 noise, 40 + 50 planted, 200 permutations. The lift is far below
the bar, so more runs wouldn't change it.

| Synthetic World | Runs | Passed Both | Typical Players Gain (Bar 2%) | Typical Trades Gain (Bar 2 Points) | β Recovered |
|---|---|---|---|---|---|
| Noise (lines mean nothing) | 5 | 0 | — | — | — |
| Planted, β₀ = 1.0 (strong) | 40 | 0 | **0.7%** | +2.8 points | 0.90 |
| Planted, β₀ = 0.5 | 50 | 0 | 0.1% | +0.7 points | 0.43 |

A smoke check on next season alone (FV1) gave the same answer: 0.6% at β₀ = 1.0.

**Reading.**
- The fit finds the planted effect (β ≈ 0.9 when it is 1.0), so the machinery works.
- But team-level context is small next to how much individual players vary. Even an effect as large as "value scales
  one-for-one with team scoring" moves the player error by under 1%. The 2% bar can't be reached with this ingredient
  at any plausible strength.
- Trades come closer (+2.8 points at β₀ = 1.0), but the rule needs both questions.
- **No real outcome was compared with any OVS-Vegas prediction.**

**What it means:** the free game lines aren't worth adding to OVS under DELTA's bar. A signal about the player himself
(his props: rushing and receiving yards, touchdowns) is the only kind that could plausibly clear it. That's the free
Odds API tier logged from now on, or a paid plan.
