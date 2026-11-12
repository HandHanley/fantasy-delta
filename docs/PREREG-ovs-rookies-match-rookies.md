# PRE-REGISTRATION — Own Value Scale: Rookies Match Rookies

**Drafted:** 12 November 2026. **Status: LOCKED 12 November 2026, with amendment A1** (weeks 5, 9, 13 and 17 pooled; §9).
Steve, 12 Nov: "let's do a rookies match test, and then we can see what this year's rookies match to in only rookies
and for rookies/sophomores". It locks by committing this
document with `study/ovs_rookies_match.py` and passing crash results, before the one real run.

---

## Plain-English Summary (For Steve)

**The question.** In season, a rookie is matched to past players who looked like him at week 9. Today that includes
second-year players, whose production number rests on a full season plus half of this one. A rookie's rests on a few
games. For Omar Cooper, 13 of 30 comparables are second-year players.

**The change.** A player in his first season with NFL games is matched only to past players in their first season with
games, at the same week. Everyone else is unchanged.

**The test.** On 2013–2022 rookies, the rookies-only version must predict the next three seasons at least 2% better
than today, with the usual permutation check, and close trades must not get worse.

**Then the page.** For this year's rookies: today, rookies + second-year only, and rookies only, side by side.

## 1. The Change, And Only The Change

- **Frame:** week 9, the adopted in-season value (`ovs_qb_starts.py` frame S): points per available game, §7, §8, no
  games number. The same 30 matches, recency weighting and FV3 outcome.
- **Who is a rookie:** a row with no NFL game in any earlier season (`rookie_Y`). That includes a player who sat out his
  draft year: his production also rests on this season alone.
- **The rule:** a rookie row's match pool keeps only rookie rows (same position, same week, seasons ≤ t − 4, as
  today). Feature scaling is done on that pool, as the matching always does on its pool.
- **Unchanged:** every non-rookie row; first-year QBs with no game (still valued as incoming rookies).

## 2. The Rows That Decide

- **Rookie rows valued from this season's games, week 9, t = 2013–2022:** 929 rows. That's 947 rookie rows minus 18
  first-year QBs with no game, which don't change.
- **Why only these:** no other row changes. Measuring over all 6,808 rows would dilute the effect about seven-fold.

## 3. The Test

- **Decides:** typical miss (RMSE, FV3), rookies-only vs today, on the 929 rows. It must be at least **2% better**, with
  paired permutation p < 0.05 (a player's rows together, 10,000 shuffles).
- **Guard:** close synthetic trades over all 6,808 test rows (rookies' values changed, everyone else's as today) no more
  than 1.0 point worse.
- **Passes →** rookies match rookies in the in-season value (Steve's OK). **Fails →** no change.

## 4. Reported, Deciding Nothing

- **The middle option:** rookies + second-year players (pool kept to rookie rows and rows with career year 2), scored
  the same way.
- **By position.**
- **What they produced ÷ value,** today and rookies-only.
- **Pool sizes:** rookie pool by position for the earliest test season (2013 rows, pool 2002–2009): QB 33, RB 216,
  WR 226, TE 118 rookie rows. Today's pool: QB 686, RB 1,548, WR 1,650, TE 925.
- **Today's page (week 9, 2026, full PPR display build):** this year's rookies under today, rookies + second-year, and
  rookies only, with values and ranks. Cooper's 30 rookie-only comparables.

## 5. Prior Looks

- **Before drafting:** for 2026 rookies only (no outcomes exist), Steve and Claude looked at value from the rookie
  comparables vs the older comparables inside today's 30. Cooper 83 vs 123, Douglas 99 vs 62.
- **After the crash test, before lock:** 2026 rookies' values under all three versions (no outcomes exist). Rookies
  only lifts most of them, Cooper included (3,797 → 4,456).
- **No historical rookie row's rookies-only value has been compared with an outcome.**
- **Known:** today's rookie rows produced 93% of their value (`PREREG-ovs-small-samples.md` §10).

## 6. Crash Tests, Before Lock

The in-season study's worlds, on the deciding rows:

- **Noise:** outcomes shuffled within position and season, both versions re-scored. It may pass at most 1 of 20.
- **Planted:** outcome = today + 0.75 × (rookies-only − today), plus the real misses shuffled within position. It must
  pass at least 80% of 200.
- **If the planted world fails,** it goes to Steve before any real run. That would mean 929 rows can't detect a real
  effect of this size.

**Results (12 Nov, `study/out/ovs_rookies_match_crash.json`):** noise passed 0 of 20. Planted passed 154 of 200 (77%,
median lift 4.1%): **FAIL**, short of 80%. Of the 46 misses, 21 had lift under 2% and 46 had p ≥ 0.05, so too few
rows to be sure is the main problem.

**Power option (`study/out/ovs_rookies_match_power_options.json`, planted world only, no real comparison):** pooling
weeks 5, 9 and 13 (the rule would apply all season) gives 2,739 rookie rows from 1,071 players, and the planted world
passes 93% of 200. Taken to Steve.

## 7. Limits

- **Week 9 only.**
- **Thin early pools:** 2013 rookies match only 2002–2009 rookies.
- **One rule for every position.**

## 8. Not Licensed Here

- **The DELTA Score, the live site and buy/sell calls.**
- **Offseason or preseason values:** incoming-rookie values already match only incoming rookies.

## 9. Amendments

**A1 (12 Nov, before lock, after the week-9 crash test failed at 77%).** Steve: "let's do the 5, 9, 13 plan. Can we
also include 17 as well". Replaces §2, §3 and §6 where they differ:

- **Deciding rows:** rookie rows valued from this season's games at weeks 5, 9, 13 and 17, t = 2013–2022: 3,981 rows
  from 1,242 players (739 / 929 / 1,071 / 1,242 by week). A player's rows move together in the permutation test.
- **Why week 17 and not 18:** through week 17 every season 2002–2022 has about 16 games per team. Week 18 exists only
  from 2021, which leaves no pool to match against.
- **Trade guard:** each week's close trades over all its test rows, pooled by trade count, no more than 1.0 point worse.
- **Crash worlds keep one outcome per player-season across weeks,** as in reality. Noise shuffles outcomes among
  player-seasons within position and season. Planted gives each player-season its rows' average of today + 0.75 ×
  (rookies-only − today), plus a real miss from another player-season at the same position.
- **Reported by week:** this shows whether the rule helps late in the season as well as early.
- **Thin pool:** the 2013 week-5 rookie QB pool is 25 rows, so those rows match fewer than 30.

**A1 crash results (`study/out/ovs_rookies_match_crash.json`):** noise passed 0 of 20. Planted passed 169 of 200
(84.5%, median lift 3.9%). PASS. The week-9-only result is kept in `ovs_rookies_match_crash_week9.json`. The 93% power
figure in §6 shuffled each row's miss on its own, which overstates power when a player has several rows. 84.5% is the
honest number.

## 10. Results (12 November 2026, One Run)

**Decision: no change.** Rookies matched only to rookies predicted **worse**. File:
`study/out/ovs_rookies_match_results.json`.

| Check | Result |
|---|---|
| Rookies only vs today (decides, 3,981 rows) | 53.69 vs 52.63: **2.0% worse**, p = 0.83 |
| Close trades (guard) | 0.5 points worse, pooled (inside the guard, but moot) |
| Rookies + second-year only (reported) | 0.2% worse: no real difference from today |

**By week (rookies only vs today):** week 5 2.7% worse, week 9 1.3% worse, week 13 2.1% worse, week 17 2.0% worse.
**By position:** QB 2.8% worse, RB 3.1% worse, WR even, TE 1.3% worse.

**What they produced ÷ value:** today 91%, rookies only 99%. On average, rookies-only values sit closer to the right
level, but they rank rookies against each other worse, so individual misses grow.

**What it means.**

- **Second-year comparables help rookies.** They widen the pool, so matches are closer on draft slot, age and
  production. A rookie-only pool is about a seventh the size.
- **Today's mix stays.** Keeping it to rookies + second-year players is no different, so there's nothing to change.
- **Week 17 tells the same story,** so late-season values aren't helped by this either.

**Today's page (reported, `study/out/ovs_rookies_match_page_2026.csv`, full PPR, ranks among all 689 players):**

| Player | Today | Rookies + Second-Year | Rookies Only |
|---|---|---|---|
| Jeremiyah Love | 4,188 (42nd) | 3,932 (45th) | 4,595 (38th) |
| Carnell Tate | 4,116 (43rd) | 4,671 (36th) | 4,313 (41st) |
| Omar Cooper Jr. | 3,797 (47th) | 3,997 (45th) | 4,456 (39th) |
| Caleb Douglas | 2,895 (64th) | 4,008 (44th) | 3,684 (48th) |
| Antonio Williams | 2,691 (65th) | 2,688 (65th) | 2,688 (65th) |
| Denzel Boston | 2,583 (68th) | 3,557 (49th) | 3,557 (49th) |
| Jadarian Price | 1,851 (92nd) | 3,337 (51st) | 3,455 (50th) |
| Makai Lemon | 1,273 (117th) | 1,910 (89th) | 1,910 (89th) |

Cooper's rookie-only comparables: 77% produced above the starter line over the next three seasons, with a median of
100. They include CeeDee Lamb, Chris Olave, Garrett Wilson, A.J. Brown, DeVonta Smith and DK Metcalf.
