# PRE-REGISTRATION — Comparables Value ("Players Like Him")

**Drafted:** 1 November 2026, before any confirmatory result exists. **Status: LOCKED** by the commit that adds this
file together with `study/comps_value_study.py` and `study/test_comps_value.py` (1 Nov 2026). The lock commit's hash
is recorded in the Project copy of this document and in `study/STUDIES.md`. Any change after that is an amendment
(§13), flagged post-lock, never a silent edit.

---

## Plain-English Summary (For Steve)

**The idea.** Price a player the way a house gets appraised: find past players who looked like him at the same point
(position, age, draft slot, recent scoring, games played, years in the league), see what they actually went on to score
over the next five seasons, flops counted as zero, and average it. FanGraphs values baseball prospects this way.

**The test.** We pretend it's each offseason from 2013 to 2020. For every player in the league that offseason, each method
guesses how much he'll be worth over the next five seasons, using only what was known then. Then we check what really
happened. The comparables method has to beat the simpler methods by a clear margin, overall and for young players, before
it can price trades. Its "chance of a starter season" has to be honest before it can appear on a card.

**What you get back.** A yes or no on three questions: is it more accurate overall, is it more accurate for young players,
and are its odds honest? Plus the real comparables for a few current players.

---

## 1. What This Study Tests, And What It Doesn't

**Tests:** whether a nearest-neighbour comparables value ("CV") predicts a player's next five seasons of fantasy value better
than simpler averages of similar past players, overall and for young players, and whether its stated odds are honest.

**Does not test, and does not license changing:** the DELTA Score (it scores demonstrated production and is untouched), the
projection, model value, buy and sell calls, or the accuracy ledger frozen on 6 Sep 2026. **No market data of any kind is
used.** FantasyCalc's terms bar using their data or "derivatives" to build a substitute for their trade calculator, and the
August study already settled market comparisons (see §2). Any product use (a Trade Calc value, a "Players Like Him" card)
needs Steve's separate approval after the results.

## 2. Prior Looks At The Data — Full Disclosure

- **August 2026, `docs/RESEARCH-market-independent-value.md`.** A market-blind value built from production and age (a
  kernel over age, projected points carried forward) beat DELTA's own baselines but lost to expert consensus in every year
  tested. Findings carried in here as fixed inputs, not re-fitted: aging works mostly through players disappearing (survival),
  not scoring less; young players' own production should outweigh draft capital after about 24 games (K = 24). Its
  do-not-retry list includes "a market-blind value built from production and age alone". **This study's comparison B2 is
  that approach, used here as a baseline, not a candidate.** The candidate adds draft capital, recency weighting, games and
  career stage, and is judged against actual outcomes, never against a market.
- **1 Nov 2026, chat illustration.** Simple bands on four current players, half PPR, outcomes through 2025:
  - Harrison-like (top-15 WRs averaging 9.3 ± 1.5 in years 1–2): 10 comparables, 70% had a top-24 season in years 3–7.
  - Lemon-like (WRs picked 10–32, rookie year 5.3 ± 2): 24 comparables, 38% had one; the median comparable produced
    nothing above the line, the mean was positive.
  - Lamb-like (WRs aged 26 averaging 13.4 ± 2): 37 comparables, 81%.
  - Javonte-like (RBs aged 25 averaging 10.9 ± 2): 36 comparables, 42%.

  These were current players, not test snapshots, but the pattern "mean above median for young players" was seen first.
  The study's young-player question is therefore partly informed by a look at the data and is stated as such.
- **1 Nov 2026, points-only Trade Calc mock.** Showed that projected-points-carried-forward gives unproven young players
  almost no value. That motivates Q2; it is not evidence.
- **1 Nov 2026, the crash tests (§13, pre-lock).** Real outcomes entered them only shuffled (noise world), through B2's own
  band averages and B2's in-sample error (planted world's base and noise size), and as one average level for top-10 picks
  (threshold world). No CV prediction was compared with a real outcome before lock.

## 3. Data (All Free, Licence Allows Use With Credit)

| File | Source (nflverse-data releases on GitHub) | Use |
|---|---|---|
| `player_stats_season.csv` | `releases/download/player_stats/player_stats_season.csv` | Season stats 1999–2024; use `season_type == REG` only |
| `stats_player_reg_2025.csv` | `releases/download/stats_player/stats_player_reg_2025.csv` | 2025 regular season |
| `draft_picks.csv` | `releases/download/draft_picks/draft_picks.csv` | Draft year, round, overall pick, position, age at draft, `gsis_id` |
| `players.csv` | `releases/download/players/players.csv` | Birth dates (`birth_date`) by `gsis_id` |

Join on `gsis_id` = `player_id`. Check that no season appears in both stats files. Credit nflverse in anything published.

**Scoring (DELTA's basis: half PPR plus TE premium).** Season points
`P = (fantasy_points + fantasy_points_ppr) / 2`, plus `0.5 × receptions` for TEs. Before anything else, verify the formula on
three known seasons by hand (one QB, one WR, one TE) and record them.

**Age.** Age on 7 Sep of the season (DELTA pins ages to that date). Missing birth date: draft age + (season − draft year);
missing both: excluded and counted.

## 4. Snapshots (The Unit Of Analysis)

A **snapshot** is one player at the end of one season `t` (the offseason). Two kinds:

- **Veteran snapshot (V):** played ≥ 1 regular-season game at QB, RB, WR or TE in season `t`. Position = his listed
  position in season `t`.
- **Incoming-rookie snapshot (R0):** drafted at QB, RB, WR or TE in the draft held after season `t` (draft year `t + 1`),
  with no NFL games yet. Position = draft position. **Every drafted player is included, busts and all.**

**Eligibility uses only what was known at the end of season `t`** (lesson 13). Nothing about season `t + 1` or later may
decide who is in.

**Features known at the snapshot:**
- **Recent production:** weighted points per game, (3 × PPG_t + 2 × PPG_t−1 + 1 × PPG_t−2) divided by the weights of the
  seasons he actually played (DELTA's 3/2/1). Season PPG counts only seasons with ≥ 1 game.
- **Games in season `t`.**
- **Age** (above).
- **Career year:** seasons since his first NFL season, with the first season = 1. R0 = 0.
- **Draft capital:** log(overall pick); undrafted = log(300).
- **Career games** `G` through season `t`.

## 5. Outcome: Future Value (FV)

For a snapshot at season `t`, using seasons `t + 1` to `t + 5`:

`FV = Σ_k 0.9^(k−1) × max(0, P_(t+k) − R_(pos, t+k))`, k = 1..5

- `P` = his season points (zero if he didn't play). **Missed time counts as zero**, which is DELTA's standing rule. This is
  not an injury lever: it is what happened.
- `R` = that season's **replacement line** at his position: the season total of the Nth-best player at the position that
  year. N = **QB 24, RB 30, WR 42, TE 14** (a 12-team superflex lineup with three flex spots). Measuring against each
  season's own line keeps eras comparable as passing grew.
- 0.9 is the same 10% per year later seasons lose in the 1 Nov mock and in Harstad's dynasty value approach. Fixed, not
  tuned.

**Secondary outcomes:** starter seasons in the window (top 24 at QB, RB, WR; top 12 at TE, by season points), and whether
he had at least one.

**Snapshot seasons:** `t` = 2001 to 2020, so every window closes by 2025.

## 6. The Methods

All four methods predict FV as **the average FV of similar past snapshots**, so they are like-for-like averages (lesson 2:
never grade an average against a median on a skewed outcome).

**The time rule, for every method (lesson 14).** To predict a snapshot at season `t`, the pool is **only snapshots from
seasons ≤ t − 5**, whose five-year futures were fully known by then, exactly as it would work live. Every scaling, band
and average is recomputed from that pool alone, separately for each `t`. A player never compares against himself.

**CV — Comparables Value (the candidate).**
- Match within position and snapshot kind (V with V, R0 with R0).
- Distance: each feature is standardised (z-scored) **within position using the pool's own spread**, then
  `d² = Σ w_f × (difference)²`.
- **V weights, fixed:** recent production 3, age 2, draft capital `1.5 × 24 / (G + 24)` (it fades with career games: the
  August K = 24 finding, applied as found, not re-fitted), career year 1, games in `t` 1.
- **R0 weights, fixed:** draft capital 3, age 1.
- **Prediction:** the plain average FV of the **30 nearest** pool snapshots. If fewer than 30 exist, use all of them (at
  least 10); fewer than 10 means the snapshot is excluded and counted.
- **Not tuned in this study.** k = 15 and k = 50 are reported as sensitivity only and decide nothing.

**B1 — Production only.** Pool average FV within position for the same recent-production band (2.0 points-a-game wide).
Fewer than 30 in a band: merge the nearest neighbouring band until there are ≥ 30. R0: the pool's R0 average at the position.

**B2 — Production plus age** (the August approach). Bands of production (2.0 wide) × age (≤ 23, 24–25, 26–27, 28–29, 30–31,
32+). Fewer than 30: widen the age band first, then production. R0: by age band.

**B3 — Draft capital only.** Bands of overall pick (1–10, 11–32, 33–64, 65–105, 106+, undrafted) × career year (0, 1, 2, 3+)
within position. Fewer than 30: merge career year first.

## 7. Test Set And Questions

**Test snapshots:** `t` = 2013 to 2020 (eight offseasons). The pool for test season `t` is every snapshot from 2001 to
`t − 5`: 2001–2008 for 2013, growing to 2001–2015 for 2020. Snapshots from 2001–2012 are only ever pool.

**Q1 — Overall accuracy.** On all test snapshots, is CV's typical miss (RMSE of predicted vs actual FV) at least 2% smaller
than **B2's**? B2 is the pre-named comparator: it is the approach CV must improve on.

**Q2 — Young players.** On test snapshots with career year 0–2 (R0 plus first and second seasons), is CV's RMSE at least 2%
smaller than **the better of B2 and B3 on these same snapshots**? Choosing the stronger baseline after seeing the results can
only make CV's job harder, so it is allowed.

**Significance, both questions:** a paired permutation test, 10,000 shuffles, **swapping the two methods' predictions for
all of a player's snapshots together** (players appear in several overlapping windows; the player is the unit, lesson 5).
Two questions are tested, so each needs **p < 0.025** (lesson 7). Lift = 1 − RMSE_CV / RMSE_baseline.

**Q3 — Honest odds (for display).** CV's "chance of at least one starter season in the next five" = the share of the 30
comparables that had one. Bin test predictions into tenths and compare predicted to observed rates. "Honest" means the
calibration error is within what a perfectly honest forecaster shows by chance (lesson 4): simulate outcomes from CV's own
probabilities 2,000 times; the real error must fall inside the simulated 95th percentile. Repeat for expected starter
seasons, by position. (Exact rule: amendment A6.)

## 8. Crash Tests, Before Lock (Lessons 1, 10, 16)

Run the full pipeline on synthetic worlds and record every result here before locking:

1. **Noise world.** Shuffle FV among snapshots of the same position and season. CV must **not** pass Q1 or Q2. If it passes
   on noise, find out why before going further.
2. **Planted world.** Build FV from B2's own prediction plus a planted extra for young players that depends on draft capital
   (an extra that B2 can't see), plus noise averaging exactly 1 (`lognormal(−sd²/2, sd)`, lesson 11), sized to the 1 Nov
   illustration's gap. CV should pass Q2 at the real sample size in at least 80% of 200 runs. If it doesn't, the study is
   underpowered for Q2 and that is reported before any real result.
3. **A world CV doesn't fit.** Outcomes driven by one sharp threshold (for example, only top-10 picks ever hit). Check that CV
   doesn't confidently report a smooth relationship that isn't there (lesson 16).
4. **Leak checks (asserted in code):** every pool snapshot for a test season `t` has season ≤ t − 5; no test player
   appears in his own pool for that season; eligibility reads nothing after `t`.

## 9. Expected Sample (Rows Counted 1 Nov 2026; No Outcomes Looked At)

- **Veteran snapshots:** players with ≥ 1 regular-season game at QB, RB, WR or TE number 458 (2001), 487 (2008), 512 (2013),
  542 (2016) and 580 (2020) a season.
- **Test seasons 2013–2020:** 4,316 veteran snapshots from 1,422 different players.
- **Incoming rookies:** 75–95 drafted at the four positions a class, so 632 R0 snapshots for draft years 2014–2021.

The study reports the real counts at every step, after its own exclusions, with each reason.

## 10. What Ships, Depending On The Result

| Result | What It Allows (Each Still Needs Steve's OK) |
|---|---|
| Q1 and Q2 pass, Q3 honest | CV can value players and picks in the Trade Calc, and a "Players Like Him" card can show odds |
| Only Q3 honest | The card can show comparables and honest odds; the Trade Calc does not change |
| Q2 passes, Q1 doesn't | Report it. Using CV only for young players is a new question, needing its own pre-registration |
| Nothing passes | Documented as a null in `study/STUDIES.md`; the idea goes back in the pocket |

## 11. Reported Regardless Of Outcome

- Counts at every stage, and every exclusion with its reason.
- RMSE, MAE and rank agreement (Spearman: "do the two lists put players in the same order") for every method, overall,
  by position and by career year (0, 1, 2, 3–5, 6+).
- The calibration table (Q3).
- k = 15 and k = 50 sensitivity (reported only, decides nothing).
- **For a fixed list of current players, named now:** Marvin Harrison Jr., Makai Lemon, CeeDee Lamb, Javonte Williams,
  Caleb Williams, Brock Bowers. Using the 2021-and-earlier pool (futures known through 2025), show their 10 closest
  comparables, what each did next, and CV's chance of a starter season. This is display material only and is produced after
  Q1–Q3. (Pool corrected to ≤ 2020: amendment A9.)
- Anything that contradicts the 1 Nov illustration, stated plainly.

## 12. How To Run This (For The Study Session)

1. Read this document and `docs/RESEARCH-market-independent-value.md`. Read the method lessons in `DELTA-HANDOFF.md`.
2. Write `study/comps_value_study.py` (pipeline) and `study/test_comps_value.py` (the §8 crash tests plus the §8.4 asserts),
   in the style of the existing study files.
3. Download the four files to a scratch folder (not the repo). Verify the scoring on three known seasons.
4. Run the crash tests. Record the results under §13 as "pre-lock".
5. **Lock:** commit this document as `docs/PREREG-comparables-value.md` together with the two scripts. Record the commit hash
   at the top of this document.
6. Run the confirmatory study once. Save results to `study/out/comps_value_results.json`.
7. Add the verdict to `study/STUDIES.md`. Report back to Steve in plain English: the three answers, one table, what to do
   next.
8. Nothing on the site changes in this session.

## 13. Amendments

### Pre-lock (1 Nov 2026) — implementation choices the text left open, decided before any CV result

- **A0. Scoring check (§3), done by hand from the raw stat lines.** Patrick Mahomes 2018 QB: standard 417.08 by hand =
  nflverse 417.08; DELTA points 417.08. Cooper Kupp 2021 WR: standard 294.5 = nflverse; PPR 439.5; DELTA points 367.0.
  Travis Kelce 2020 TE: standard 207.76 = nflverse; DELTA points 312.76 (half PPR + 0.5 TE premium = full PPR for a TE).
  No season sits in both stats files. Veteran row counts match §9 exactly (458 / 487 / 512 / 542 / 580).
- **A1. Draft capital.** Read from `draft_picks.csv` by `gsis_id`; `players.csv` draft fields as fallback (4 players).
  Picks after 300 (pre-1994 twelve-round drafts, veterans only) are capped at log(300); B3's undrafted band is a separate
  flag, so a pick-326 veteran sits in "106+", not "undrafted".
- **A2. Rookies with no age.** 72 drafted players (2002–2015 classes, almost all rounds 5–7) have neither a birth date nor a
  draft age, and **none of them ever played**. §3 says exclude; §4 says every drafted player is included, busts and all
  (lesson 8). Excluding them would delete only busts, so §4 wins: each gets the median draft age of his class and position.
  Counted in the results (`R0_age_imputed`).
- **A3. Ages.** Veteran: 7 Sep of season `t`. Incoming rookie: 7 Sep of his rookie season `t + 1`. Rookies only ever compare
  with rookies, so the choice is consistent within kind.
- **A4. Career year and career games.** First NFL season = the earliest of draft year, first season with a game, and
  `players.csv` rookie season (each only if ≤ `t`). Career games count from 1999, where the data starts: 1,032 veteran
  snapshots belong to careers that began earlier, so their `G` is undercounted (this only affects how fast draft capital
  fades for those veterans).
- **A5. Positions in outcomes.** Each future season's points are scored by his listed position that season (TE premium for
  TEs). The replacement line and the starter line come from the snapshot position, the position the forecast is about. A
  starter season needs points above zero.
- **A6. Q3, exact rule.** Chance of a starter season: bins are tenths of probability (0–0.1 … 0.9–1.0). Expected starter
  seasons: bins are tenths of the test sample by predicted value (deciles). Calibration error = the count-weighted average
  gap between predicted and observed in each bin. The honest forecaster draws each test player's outcome from his own 30
  comparables, 2,000 times. **Q3 is honest if** both measures pass overall at the 95th percentile **and** all eight
  position checks (four positions × two measures) pass at the 99.375th percentile (the 5% shared across eight checks). A
  95th-percentile bar on all ten checks would fail a perfectly honest forecaster about four times in ten.
- **A7. Distance details.** The draft-capital fade uses the appraised player's own career games. Z-score spreads come from
  the whole pool for that season, position and kind. "Never compares against himself" removes all of the player's own
  earlier snapshots from his pool, for every method.
- **A8. Band growth.** "Nearest neighbouring band" = the adjacent band whose midpoint is closer to the player's value. B2
  widens age one band at a time until every age is in, and only then widens production (all ages). B3 widens career year
  first, then pick band. B1 and B2 match kind (veterans with veterans; rookies by the R0 rules); B3 crosses kinds through
  career year, so a rookie band short of 30 can borrow first-year veterans, as the text implies.
- **A9. Current-player pool.** §11 says "2021-and-earlier pool (futures known through 2025)", but a 2021 snapshot's window
  runs to 2026 and is not complete. The pool is snapshots ≤ 2020, which is also the live time rule for an end-of-2025
  appraisal.
- **A10. Crash-test worlds, exact construction.** Planted world: base = B2's band average for every 2001–2020 snapshot from
  all other players' snapshots (no time rule; it is a synthetic world, not a forecast). Young players (career year ≤ 2) get
  a multiplier `pick^−β`, averaging 1 across young players, with β set so the average for picks 1–10 is 70/38 = 1.84 times
  the average for picks 11–32 (the 1 Nov Harrison-like vs Lemon-like gap). Noise is `lognormal(−sd²/2, sd)`, with sd set so
  the synthetic world scatters around its own truth as far as real outcomes scatter around B2's band averages. (A first
  smoke run sized the noise to the raw outcome spread instead, giving sd 0.46 — far cleaner than reality, which would
  overstate power. Corrected before the 200 runs; lesson 15.) Threshold world: only top-10 picks ever produce, at their
  position's real average level times lognormal noise; everyone else is zero. Flag if CV's average for picks 11–15 is more
  than 30% of its average for picks 6–10.

### Pre-lock crash-test results (1 Nov 2026, `study/out/comps_value_crash.json`)

Sample after exclusions: 10,187 veteran and 1,605 rookie snapshots (2001–2020); test set 4,316 veteran + 632 rookie =
4,948 snapshots from 1,582 players (the §9 figure of 1,422 counted veterans only). Every test snapshot had at least 10
comparables; nothing was excluded.

1. **Noise world — passed (CV did not pass on noise).** 20 shuffles: Q1 passed 0 times, Q2 passed 0 times. Average lift
   −0.8% (Q1) and −1.0% (Q2); the best single run was −0.1%, smallest p 0.60.
2. **Planted world — powered.** 200 runs: CV passed Q2 in **91%** (bar 80%), median lift +5.2%; the stronger young baseline
   was B2 in 198 runs. β = 0.33, noise sd = 0.69. CV also passed Q1 in 54% of runs.
3. **Threshold world — FLAGGED.** When only top-10 picks ever produce, CV smears the cliff:

   | Young players, by pick | Truth (avg FV) | CV | B3 |
   |---|---|---|---|
   | 1–5 | 134.5 | 75.5 | 128.0 |
   | 6–10 | 109.4 | 44.7 | 103.5 |
   | 11–15 | 0 | 29.0 | 0 |
   | 16–20 | 0 | 12.2 | 0 |
   | 21–32 | 0 | 4.7 | 0 |
   | 33–64 | 0 | 1.2 | 0 |

   CV values picks 11–15 at 65% of picks 6–10 (flag at 30%), and undervalues the real hits by about half. Reason: there
   are only a handful of top picks per position per class, so a player's 30 nearest rookies span most of round one. This
   is a property of a fixed 30-neighbour average, not a bug. **Not corrected:** §6 forbids tuning k, and changing the
   design on one synthetic world would be tuning. Consequences for reading the result: if real outcomes have a sharp
   premium at the very top, CV loses to B3 on young players and its odds for top picks run low; Q2 and Q3 will show it.
   Any future "Players Like Him" card should not show a top-10 pick's comparables without saying how far down the board
   they reach.
4. **Leak checks — passed.** Asserted on every test row: pool seasons ≤ t − 5; the player is in none of his own pools
   (CV at k = 15, 30, 50; B1; B2; B3). Rebuilding the snapshots with every season after T deleted gives identical
   eligibility and features at T = 2008 (574 snapshots), 2013 (589), 2016 (625) and 2020 (655).

### Post-lock

- **A11 (post-lock, 1 Nov 2026, found after the confirmatory run). Positions.** The display list for Brock Bowers showed
  Tim Tebow and Jordan Matthews as comparables. Cause: nflverse's season stats file puts a player's **latest** position on
  every season (Tebow's 2010–11 QB seasons read TE; Matthews' WR seasons read TE), and leaves some seasons blank (Trent
  Richardson 2012–13), so §4's "listed position in season `t`" was not what the locked run used. 597 player-seasons in
  2001–2020 differ from that season's nflverse roster file. This hits every method identically, so the comparison stays
  fair. **The locked run remains the verdict of record.** Rule set before re-running: re-run once with each season's
  position from `roster_YYYY.csv` (falling back to the stats file); if any answer flips, that answer is reported as
  unsettled. Code: `--rosters DIR`; the default path was checked to reproduce the locked output exactly.
  **Result: no answer flips** (Q1 +5.2%, Q2 +6.7%, both p < 0.001; Q3 not honest). The current-player display uses the
  roster-position run.

### Results (1 Nov 2026) — `study/out/comps_value_results.json`, `study/out/report_comps_value.txt`

| Question | CV | Baseline | Lift | p | Answer |
|---|---|---|---|---|---|
| Q1, all 4,948 test snapshots | 74.4 | B2 78.9 | +5.7% | < 0.001 | **Pass** |
| Q2, career year 0–2 (2,090) | 79.6 | B2 85.7 (B3 85.8) | +7.2% | < 0.001 | **Pass** |
| Q3, honest odds | — | — | — | — | **Not honest** |

- **Q3:** odds run high in the middle (said 35%, happened 27%; said 43%, happened 34%). Honest only at RB. For veterans the
  average chance runs about 4 points high in every test year; incoming rookies run slightly low.
- **Incoming rookies alone (career year 0), stated plainly:** draft-slot bands beat CV (B3 84.3 vs CV 87.5). Consistent with
  the threshold-world flag (untested as the cause). CV's young-player win comes from first- and second-year players.
- **§10 did not anticipate this combination** (accuracy passes, odds do not). Reading it: the accuracy result is what a
  Trade Calc value would rest on; the odds result bars showing a "chance of a starter season" on a card. Either use needs
  Steve's approval.
- **1 Nov illustration:** consistent for Harrison (illustration 70%, CV 67%), Lamb (81% vs 83%) and Javonte (42% vs 40%);
  Lemon higher (38% vs 50%), but the two use different windows (years 3–7 vs the next five) and groups (picks 10–32 vs his
  30 nearest rookies). Given Q3, the three veterans' odds likely run a few points high; incoming rookies' ran slightly low. Young players' FV mean
  37.2 vs median 0, as seen.
