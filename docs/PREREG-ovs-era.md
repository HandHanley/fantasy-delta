# PRE-REGISTRATION — Own Value Scale: Era-Adjusted Matching

**Drafted:** 7 November 2026. **Status: LOCKED 8 Nov 2026 (amendments A1, A2).** Locks by committing this document with `study/ovs_era.py`
and its crash results, before the one real run. Changes after that are amendments (§9).

Changes one thing in `docs/PREREG-own-value-scale.md` (locked `63c80df`, passed 7 Nov).

---

## Plain-English Summary (For Steve)

**The bug.** The Own Value Scale finds a player's matches by his recent points per game. But scoring levels have moved:
the average starting QB scored 14.4 points a game in 2008 and 17.6 in 2025, while running backs stayed near 14.6. So a
QB12 today (Baker Mayfield, 17.9 over his last three seasons) gets matched with the QB3s of 2008 (Brees, Manning, Brady)
and borrows their next five years. Running backs get the opposite.

**The fix.** Measure each season's production against that season's typical starter at his position, before matching.
"17.9 points a game" becomes "1.02 times a typical starting QB that year", which is what it really was.

**The test.** The same test seasons, outcome and scoring as the Own Value Scale. Does the fixed version predict players'
next five seasons at least 2% better than the current one?

## 1. The Change, And Only The Change

- **Starter level** for season `y` and position: the average points per game of the top 24 QBs, RBs or WRs, or the top
  12 TEs, among players with 8+ games that season (half PPR, TE premium, as everywhere).
- **Era-adjusted production** = the same 3/2/1 weighting over seasons `t`, `t − 1`, `t − 2` that the locked feature uses,
  but of `(his points per game that season) ÷ (that season's starter level at his position that season)`. Same seasons
  counted, same games, same weights.
- **Unchanged:** rookies (draft slot and age; their matches are asserted identical), age, games, draft slot (Version A),
  career year, the matching weights, 30 matches, Fix 2 weights (half-life 8), 12-team superflex lines. **Outcome, pool
  and test seasons per amendment A1:** the next three seasons (FV3), pool `≤ t − 3`, test seasons 2013–2022.

## 2. The Questions

- **Q1 (decides, per A2):** on the **754 veteran QB** test snapshots, RMSE on FV3 (A1) of the era version vs the locked
  matching; and on all 6,484, no more than 0.5% worse. Paired
  permutation test on the QB rows, 10,000 shuffles, a player's snapshots swapped together, one-sided. **Pass: QB lift
  ≥ 2% and p < 0.05, and all rows no more than 0.5% worse** (DELTA's model-change rule on where the change acts).
- **Q2 (guard):** the OVS study's synthetic trades, rebuilt from these two methods' predictions with the same rules and
  seed. The era version may not call them more than 1.0 point worse (point estimate).
- **Decision:** Q1 passes and the guard holds → era-adjusted matching replaces the locked matching in the Own Value Scale
  (Steve's OK). Otherwise the locked matching stays, and the QB problem goes to another fix.

## 3. Reported, Deciding Nothing

- Produced ÷ predicted by position, for veterans valued above 60 (both versions). Today: QB 0.76, RB 0.85, WR 0.83,
  TE 0.95.
- Q1 by position and by age.
- Today's values (2025 snapshots) on the 0–10,000 ruler for the top 25 and named players, Baker Mayfield's new matches.

## 4. Prior Looks — Full Disclosure

- The locked OVS results on these test seasons are known (OVS beat production + age by 6.2%).
- 7 Nov, this chat: QB calibration (above) and Baker Mayfield's 30 matches were looked at, which is what found the bug.
  The produced ÷ predicted figures are a look at test outcomes **under the locked method**; no era-adjusted prediction
  has been compared with any outcome.
- Steve's eye test (7 Nov): QBs far too high; Baker is "much closer to 90th than 3rd".

## 5. Crash Tests, Before Lock

Using the real data and both methods' real predictions:
1. **Noise world:** outcomes shuffled within position and season (pool and test). The era version may pass Q1 in at most
   1 of 20 runs.
2. **Planted world:** truth = max(0, locked + w × (era − locked) + leftover error), with the leftover errors around the
   locked version shuffled within position. **w = 0.75 must pass Q1 in ≥ 80% of 200 runs**; w = 0.6 reported.
3. **Leak checks (asserted in code):** pool `≤ t − 5`, no player matched to himself, rookie matches identical, the locked
   OVS reproduced row for row.

1,000 permutations per crash run (10,000 in the real run).

## 6. Limits, Stated Now

- Five seasons ahead only, 12-team superflex lines, as the OVS.
- It fixes the era of the *matching*. It does not add this season's games: that's Plan 2
  (`docs/PREREG-ovs-in-season.md`).
- A single starter level per position-season; it doesn't adjust for team or offense.

## 7. What Each Result Allows (Steve's OK Needed)

| Result | Allows |
|---|---|
| Q1 passes, guard holds | Era-adjusted matching becomes the Own Value Scale; pick values re-measured on it |
| Q1 fails | The locked matching stays; the QB problem needs another fix |

## 8. Not Licensed Here

The DELTA Score, the site's model value, buy/sell calls. Nothing on the site changes.

## 9. Amendments

**Before lock**
- **A1 (7 Nov, Steve): value looks three seasons ahead, not five.** "We should be valuing at the next 2-3 years as our
  North Star. That's the discipline we've used in different other areas of DELTA. Five years is too long." So, for both
  versions: outcome FV3 = Σ 0.9^(k−1) × max(0, points − replacement line) over seasons t+1..t+3 (the same window as
  Historical Comps); pool `≤ t − 3`; test seasons 2013–2022 (6,484 snapshots, 1,890 players); "valued above 60" in §3
  becomes "above 35" (three-season units). Reported only: each version against production + age, since the Own Value
  Scale's pass (6.2%) was measured on five seasons. The crash tests below were rerun on this outcome; the five-season
  crash results are kept for the record. The preview below was on five seasons.
- **Crash tests on three seasons (7 Nov, `study/out/ovs_era_crash.json`; the five-season run is in git history):**
  noise world 0 of 20 (pass); planted w = 0.75 passed Q1 in only **96 of 200 (48%, bar 80%)**, typical lift 1.97%;
  w = 0.6: 0 of 50. **FAIL.** Over three seasons the two versions differ less across all players, so even a clearly
  better version shows about a 2% gain, on the bar. The change acts mostly on QBs: average change in prediction 17.4
  on an average of 73 for veteran QBs, against 3–5 for RBs, WRs and TEs.
- **A2 (8 Nov, Steve chose it: "Let's do option A"):** decide on veteran QBs (754 rows), where the fix acts. Pass: QB
  lift ≥ 2%, p < 0.05, **and** all rows no more than 0.5% worse, **and** the trade guard. Its crash test, same worlds:
  planted w = 0.75 passed **176 of 200 (88%)**, typical QB lift 4.3%; w = 0.6 passed 17 of 50; noise world 0 of 20.
  Rerun from the committed code (8 Nov, `study/out/ovs_era_crash.json`): identical, 0 of 20 / 176 of 200 / 17 of 50.
  **PASS.**
- **Crash tests (7 Nov, `study/out/ovs_era_crash.json`):** noise world passed Q1 in **0 of 20** (bar ≤ 1); planted
  w = 0.75 passed in **198 of 200** (bar 80%), typical lift 3.5%; w = 0.6 passed 26 of 50, typical lift 2.1%. **PASS.**
- **Preview of today's values (7 Nov), disclosed.** Before asking for the OK to run, today's 2025 values were computed
  both ways (pool ≤ 2020; no test-season outcome involved). Baker Mayfield: #3 → #14 among site players; his matches are
  now Garrard, Delhomme, Plummer, Kitna, Hasselbeck, Tannehill and similar, where they were Brees, Manning, Brady.
  QBs' average rank among FantasyCalc's top 150: 54 → 64 (FantasyCalc 63). Unchanged: young QBs at the very top (Dart
  #2, Maye #3, Hurts #4, Caleb Williams #5, Nix #6); RBs (117 vs FantasyCalc 77) and TEs (140 vs 90) far below the
  market; overall rank agreement with FantasyCalc 0.705 → 0.704.

## 10. Results (8 Nov 2026, Run Once)

`study/out/ovs_era_results.json`. **Passed. Era-adjusted matching replaces the locked matching** (Steve's OK given
before the run, "Let's do option A").

| Question | Era-Adjusted | Locked Matching | Result |
|---|---|---|---|
| Veteran QBs (754 rows): typical miss (RMSE, FV3) | 83.7 | 88.3 | **5.3% better, p = 0.003** (bar 2%, p < 0.05) |
| All 6,484 rows | 51.5 | 52.4 | 1.7% better (guard: no more than 0.5% worse) |
| Close synthetic trades called right (23,347) | 55.7% | 54.4% | +1.2 points, p = 0.13 (guard: no more than 1 point worse) |

**Reported, deciding nothing.**
- Against production + age on three seasons: locked matching 5.9% better, era-adjusted **7.5% better** (both p ≈ 0.0001).
  So the Own Value Scale's pass holds on the three-season outcome, and the fix adds to it.
- Produced ÷ predicted, veterans valued above 35: QB **0.83 → 1.06**, RB 0.84 → 0.81, WR 0.85 → 0.88, TE 0.87 → 0.99.
  QBs are no longer overvalued; if anything slightly under.

**Today's values (2025 snapshots, pool ≤ 2022), display only.** Agreement with FantasyCalc's top-150 order 0.708 → 0.721.
Baker Mayfield #3 → #17; Jared Goff #6 → #23; Mike Evans #256 → #174. Still unlike the market: young QBs at the top (Jaxson
Dart #2, Jalen Hurts #3, Drake Maye #4), and RBs (average rank 113 vs FantasyCalc 77) and TEs (139 vs 90) low. In 2026 to
week 9: Gibbs RB1, Bowers TE1, McBride TE2, Smith-Njigba WR1; Mayfield QB36, Nix QB23, Hurts QB17; Dart has played two
games. That is Plan 2's subject (`docs/PREREG-ovs-in-season.md`).

**Consequence:** every pick-value number built on 7 Nov used the five-season, locked-matching ruler. They are re-measured
once the value settles (after Plan 2).
