# PRE-REGISTRATION — In-Season Production Blend

**Written:** 25 September 2026; data checks added 26 September. No outcome for this question has
been looked at: the only runs were `--count` (eligibility, no errors) and a code check with every
outcome replaced by random numbers.
**Script:** `scripts/blend-study.py` — `--count`, then `--run`, which refuses unless this file is
committed and unedited.
**Status:** DRAFT for Steve's review. Locks on commit. Changes after the first confirmatory run
must be recorded as amendments at the bottom, with a reason, not edited in silently.

---

## 1. What Is Already Decided, And Is NOT On Trial

**Decided 25 Sep 2026 (Steve):** the freeze is the ledger's fixed record, not a freeze on the live
site. Live projections and buy/sell calls should react to what happens this season. The DELTA Score
does not react to weekly stats (it measures completed seasons), although contracts still move it.

Today, the only way this season's games reach the projection is a blunt one: a penalty that counts
how often a player's last 34 games fell below a usable-starter line, in steps at 40/45/55/65%.
His 2026 points per game never enter the projection directly. Jerry Jeudy's projection moved 2%
after three quiet weeks (6.01 → 5.89); Josh Downs flipped Hold → Buy on one decent game crossing
the 65% step.

**This study tests one thing: how much weight this season's production should get, and when.**
It does not decide whether in-season data belongs in the projection. That is already decided.

**If nothing clears the bar, nothing ships.** The ship gate is a platform non-negotiable. The
current behaviour stays, and the result is recorded as a null.

---

## 2. Prior Work — Full Disclosure

No analysis of in-season weekly outcomes has been run for this study. What has been seen:

- **K = 24 study (Aug 2026)** — a different question, same shape. It blended a young player's own
  production against his draft-slot prior with `weight = games ÷ (games + K)` and found K = 24
  beat both pure strategies (RMSE 4.177 vs 4.620 and 4.748). This is why the blend form below is
  the primary contender. It is a prior, not a result for this question.
- **Miss % study (10 Aug 2026)** — season-to-season, not within a season. Miss % added +2.0%
  pooled but reversed with the transition order and hurt RB, TE and QB. Not shipped. Disclosed
  because the live step penalty is a version of the same idea.
- **Anecdotes (25 Sep 2026)** — Pickens, Jeudy, Downs. These motivated the study and are not data.
- **The Start Profile's usable-starter lines** (`data/start-profile-thresholds.json`, generated
  10 Jun 2026) were set from 2023–2025 games, which overlap the held-out seasons. They are the
  definition of "usable starter", not fitted to predict anything, and contender D uses them
  exactly as the live engine does. Disclosed because the overlap is real.

---

## 3. The Question

At a checkpoint in the season (after Week **3, 6, 9 and 12**), which predicts a player's points
per game **for the rest of that regular season** better:

- **A — Preseason only (today's core).** The projection made before Week 1, held all season.
- **B — Blend.** Preseason projection mixed with his points per game so far this season.
- **D — Blend plus the live step penalty.** B, with the engine's Start Profile penalty on top.

**Scoring:** half-PPR with tight-end premium (the model's `half_tep` basis, same as
`scripts/backtest.js`).

**Who is graded at a checkpoint:** QB/RB/WR/TE with a preseason projection (the backtest rule:
≥8 games across the prior three seasons), **≥1 game played by the checkpoint**, and **≥4 games
played after it**. Players with zero games by the checkpoint are left out: A and B are identical
for them, so including them only dilutes the comparison.

**What "better" means:** the typical size of the miss (RMSE) on rest-of-season points per game.

---

## 4. The Contenders

**A — Preseason only.** `scripts/backtest.js`'s projection core: the 60/30/10 blend of the three
prior seasons, each shrunk by `min(1, games/8)`. Held fixed through the season.

**B — Blend (can ship).**

```
blended = w × (PPG so far this season) + (1 − w) × preseason
w       = G ÷ (G + K)        G = games played so far this season
```

Three games barely move it; ten games move it a lot. **K is chosen once, by cross-validation inside
the training seasons only,** from this fixed grid: 4, 6, 8, 10, 12, 16, 20, 24, 32. One K for all
positions; a per-position K is not tested here (that is how the Aug miss% result fooled us).

**D — Blend plus the live step penalty (can ship; added 26 Sep at Steve's request).** B, then the
engine's Rule 4 on top, exactly as `calcProj` applies it: `× (1 + 0.5 × d_volatility)`, where
`d_volatility` comes from Miss %/Elite % over the player's last 34 played games as of the
checkpoint (crossing into prior seasons, as the live Start Profile does), only when he has ≥20
games: −9/−6/−3/−1% at miss above 65/55/45/40%, eased by +3%/+1% at elite above 30/20%. K is
tuned separately for D. **This is the double-counting question:** if the penalty adds something
the blend doesn't already capture, D wins; if it just re-counts the same games, B wins.

**C — Rolling games (exploratory; reported, cannot ship from this study).** The preseason
projection counts as K pretend games. This season's real games are weighted so each older game
counts for less (half-life of H games, H chosen from 4, 8, 16 inside training). This is Steve's
"a huge game 35 games ago doesn't matter anymore" idea in its purest form. If C beats B on the
held-out seasons, it earns its own pre-registration; it does not ship off the back of this one.

---

## 5. Data And Split

- **Source:** nflverse weekly player stats (the feed `fetch-backtest-data.py` loads) and nflverse
  snap counts, 2015–2025 regular season, so every target season has three prior seasons.
- **A played game** is the live DNP rule from `fetch-game-logs.py`: at least one offensive snap OR
  any recorded production. Used for **everything** — prior seasons, games so far, games after.
  `backtest.js` counts "has a stats row" instead; mixing the two would make A look high and hand
  the blend a free win. 11,784 of 67,793 played games had zero production and only the snap rule
  catches them.
- **Players are tracked by nflverse ID, never by name** (two Josh Johnsons and two Ryan Griffins
  exist in this data). Snaps join by ID through nflverse's players table; 110 snap rows had no ID
  match and are dropped.
- **Scoring:** A, B, C and the outcome use `backtest.js`'s formula. D's penalty classifies games
  with the engine's own `gamefp()` (which also counts fumbles, two-point plays and return TDs),
  exactly as the live Start Profile does.
- **Training seasons (K and H chosen here):** 2018–2022.
- **Held-out seasons (evaluated ONCE):** 2023–2025. Nobody looks at held-out outcomes before K is
  locked from training.
- The graded count per checkpoint will be printed and recorded here **before** any error is
  computed.

This is the same shape as the `ROOKIE_PPG` validation (fit on older years, grade once on the
latest three).

---

## 6. The Pass Mark

**Choosing between B and D happens on the training seasons only:** whichever has the lower
training RMSE (each at its own best K) is the candidate. Only the candidate faces the gate below.
Both are reported on the held-out seasons for information; the held-out numbers cannot swap them.

All four must hold on the held-out seasons, or the candidate does not ship:

1. **Size:** the candidate's RMSE is **at least 2% lower** than A's, pooled across the four checkpoints
   (each checkpoint weighted equally).
2. **Not a fluke:** permutation **p < 0.05**, 2,000 shuffles, seed 20260926, one-sided,
   p = (shuffles at least as good + 1) ÷ 2,001. Shuffles swap A's and the candidate's errors
   within **player-seasons**, not rows, because one player appears at up to four checkpoints and
   those rows are not independent.
3. **Every held-out season:** the candidate beats A in each of 2023, 2024 and 2025 on its own. A lift carried
   by one season is exactly what reversed on us in August.
4. **No position is harmed:** the candidate is no more than 1% worse than A at any single position.

**K is chosen by leave-one-season-out inside 2018–2022** (the out-of-fold error picks between B
and D); the final K is the best over all five training seasons.

**Reported only, never gated:** the same comparison limited to players projected at 8+ points
preseason (roughly the rostered range), so a win carried by deep backups is visible as such.

Expected, stated in advance so it can be wrong: little or no lift at Week 3, growing through
Week 12. A lift that is biggest at Week 3 would be suspicious and investigated before shipping.

---

## 7. What Ships If It Passes

1. `calcProj` blends this season's points per game (from `game-logs.json`, current season only)
   into the base at the locked K.
2. **No double counting, decided by the data:** if B is the candidate, the projection's step
   penalty stops reading current-season games in the same change, so a 2026 game enters the
   projection once. If D is the candidate, both stay, because the test showed the penalty adds
   something. (Decided 26 Sep: let the test choose.)
3. Engine Audit must read 32/32 with no opposite-direction flags, and the ledger is untouched
   (it grades the frozen file).

---

## 8. Not Tested Here

- **Buy/sell calls.** Model value is the market price adjusted by small percentages; the
  projection reaches it only through a starter/elite tier bonus. **A better projection will barely
  move buy/sell calls by itself.** Making calls react needs a second, separate term, such as
  "running ahead of or behind his preseason projection". It cannot be backtested the same way,
  because historical market prices only exist from 2026. It needs its own design and its own
  decision, after this study.
- **Usage** (snap share, target share). Usage settles in a few games while points stay noisy
  (backlog §5.2), so it may be the better early signal. That is a second study; mixing it into
  this one would test two things at once.
- **The step penalty in model value** (`d_vol_mv`). D tests Rule 4 in the projection only.
- Situational multipliers, ripples, QB quality — cannot be reconstructed for past seasons.

---

## Pre-Lock Checks (26 September 2026)

Every piece was checked against the real code before this was locked:

| Check | Result |
|---|---|
| Season totals rebuilt from weekly data vs `data/backtest-data.json` | 4,737 of 4,762 identical; the rest are nflverse relabels since June (fullbacks, Travis Hunter as CB, Kenny Gainwell) and two small stat corrections |
| A vs the real `backtest.js` (2025, same game definition) | 327 of 332 identical; the 5 are the same relabels |
| D's Miss %/Elite %/games vs the engine's own Start Profile at the freeze | 305 of 305 identical (23 skipped for name spelling only) |
| `--run` refuses when this file is uncommitted, and when it has uncommitted edits | Both refused |
| Full `--run` path with every outcome replaced by random numbers | Runs end to end; noise fails the 2% bar, as it should |

**Graded player-checkpoints** (printed by `--count` before any error was computed):

| Season | After Week 3 | After Week 6 | After Week 9 | After Week 12 |
|---|---|---|---|---|
| 2018 | 283 | 276 | 259 | 228 |
| 2019 | 296 | 285 | 261 | 234 |
| 2020 | 315 | 311 | 294 | 254 |
| 2021 | 323 | 326 | 307 | 268 |
| 2022 | 314 | 312 | 297 | 265 |
| **2023** | 311 | 317 | 304 | 269 |
| **2024** | 330 | 325 | 318 | 281 |
| **2025** | 302 | 307 | 303 | 277 |

Training 5,708 rows; held out (bold) 3,644 rows from 1,060 player-seasons. The step penalty is
active on 6,907 of 9,352 rows.

## Amendments

**1 — 26 Sep 2026, after the result, before shipping: where the blend sits in `calcProj`.**
§7 said "blends this season's points per game into the base". Built literally, the blended number
would then pass through the situational multipliers (team system, play-caller, QB quality), which
multiplies 2026 points that were already scored in that system with that QB — the team situation
counted twice, and not what was tested. The study's form was
`(w × this-season PPG + (1 − w) × preseason projection) × (1 + 0.5 × d_volatility)`, so that is what
shipped: the live preseason projection is rebuilt without the volatility term, blended at K = 4, and
the term applied once to the result. Eligibility follows the study: ≥8 played games in the three
prior seasons (counted from `game-logs.json`), so rookies keep today's path. Points use the site's
`gamefp()` in the selected format, which also counts fumbles, two-point plays and return TDs.
**Also found while building, not tested here:** "FIX 2" in `calcProj`, a hard projection ceiling for
Miss % above 55/65, reads the same Start Profile. It is left exactly as it was.

## Result (26 September 2026) — PASSED, ship

Run once, `python3 scripts/blend-study.py --run`, against this file as committed in `0398624`/`c164ba0`
(sha256 prefix `774542360bd0403e`). Nothing above this section was changed after the run.

**The candidate, chosen on training seasons only, was D (blend plus the live step penalty) at K = 4.**
Training out-of-fold typical miss: B 3.212, D 3.207, C 3.201 (exploratory). D edged B by 0.005 — a tie
in practice — so under §7 the step penalty stays.

| Held-Out (2023–2025) | Typical Miss (RMSE, PPG) | Better Than Preseason Alone |
|---|---|---|
| A — preseason only | 3.810 | — |
| B — blend | 3.186 | 16.4% |
| **D — blend + penalty (candidate)** | **3.186** | **16.4%** |
| C — rolling games (exploratory) | 3.185 | 16.4% |

**Gates, all passed:** size 16.4% (bar 2%) · p = 0.0005, 0 of 2,000 shuffles as good (bar 0.05) ·
every held-out season (2023 21.8%, 2024 14.1%, 2025 13.1%) · every position (QB 13.1%, RB 19.6%,
WR 17.2%, TE 13.6%; bar −1%).

**By checkpoint:** Week 3 13.3%, Week 6 14.4%, Week 9 17.3%, Week 12 19.9% — growing through the season
as §6 predicted, not peaking early. **Rostered range only (8+ PPG preseason, reported, not gated):**
B 14.5%, D 14.8%, C 14.5%.

**K = 4 sits at the bottom of the grid, so it was checked afterwards on training seasons only** (not
part of the decision): K = 2 3.277, 3 3.227, **4 3.211**, 6 3.221, 8 3.251. A genuine peak, flat
between 3 and 6. At K = 4 this season counts 43% after 3 games, 60% after 6, 69% after 9.

**What this does NOT show:** A is the projection *core*. The live preseason projection also carries
the situational multipliers, so the live gain will be smaller than 16%. And only players who played
4+ more games are graded — someone benched for good after Week 3 has no outcome to score.

**Penalty verdict:** blend alone and blend plus penalty are indistinguishable (held-out 3.1855 vs
3.1862). The penalty neither helps nor hurts once the blend is in; it stays because the pre-set rule
picked D on training.
