# PRE-REGISTRATION — Own Value Scale: This Season's Games

**Drafted:** 7 November 2026. **Status: DRAFT, NOT LOCKED.** Builds on `docs/PREREG-ovs-era.md` (passed 8 Nov: era-adjusted matching, three
seasons). Locks by committing this document with `study/ovs_in_season.py` and its crash results, before the one real run.

---

## Plain-English Summary (For Steve)

**The gap.** The Own Value Scale only knows full seasons. In November 2026 it still values players on 2023–2025, so a
QB who has been QB30 for seven weeks (Baker Mayfield, 10.4 points a game) looks the same as in August.

**The fix.** Count this season's games so far as the newest season, updated every week, exactly how the other chat's
in-season Historical Comps study did it. A player at week 9 is matched against past players at week 9 of their own
seasons, so a hot or cold half-season is compared with other hot or cold half-seasons, not with full seasons.

**The test.** At weeks 5, 9 and 13 of past seasons, does counting the season so far predict the next three seasons at
least 2% better than ignoring it (what the value does today)?

## 1. Snapshots

From `study/comps_in_season.py`'s `snapshots()` (locked with `docs/PREREG-in-season-comps.md`), unchanged in what it
counts:
- **A player at the end of week W of season Y**, W = 5, 9, 13. Weekly nflverse files 1999–2026 (a game = a week with a
  pass, carry, target or catch, as that study found matches the season file 96.8% of the time).
- **In-season version:** this season so far is the newest season in the 3/2/1 production; games = games so far; this
  season's rookies are year-1 veterans (production, games, age, draft slot).
- **Baseline (what the value does mid-season today):** this season ignored; 3/2/1 over the last three full seasons;
  games = last season's; this season's rookies matched as at the draft.
- **Production is era-adjusted in both** (it passed): each season's points per game ÷ that season's starter level at
  his position — the average points per game of the top 24 QBs/RBs/WRs or 12 TEs with 8+ games, from the weekly file;
  for this season, the same through week W among players with at least half the weeks so far (3 at week 5, 5 at week
  9, 7 at week 13).
- Age and career year are the same in both.

## 2. Matching And Outcome

- Version A, 30 matches, Fix 2 weights, as the Own Value Scale. A row at week W of season Y is matched only against pool
  rows at **the same week W** of seasons **≤ Y − 4** (their three seasons ahead had finished by Y − 1, before week W of
  Y), from 2002 (the first season with three seasons of weekly data behind it).
- **Outcome:** FV3 over seasons Y + 1 to Y + 3 (Steve, 8 Nov: three seasons), 12-team superflex lines, half PPR + TE
  premium, from the season file. Checked identical to the era study's outcome on all 10,604 shared rows. The rest of
  season Y isn't counted, in either version.
- **Test seasons:** Y = 2013–2022 (week 9: 6,808 rows, 1,829 players, 947 of them in their rookie season).

## 3. The Questions

For each week W (5, 9, 13), on the same rows:
- **RMSE of the in-season version vs the baseline.** Paired permutation test, 10,000 shuffles, a player's rows swapped
  together, one-sided. **Pass: lift ≥ 2% and p < 0.0167** (0.05 split across three weeks).
- **Guard:** synthetic trades built as in the Own Value Scale study; the in-season version may not call them more than
  1.0 point worse.

**Decision:** the value counts this season's games from the first tested week that passes, and every later week
(e.g. 9 and 13 pass, 5 fails → from week 9). Before that week, and if none pass, it stays on full seasons.
Weeks between test weeks follow the week before (week 10 follows week 9).

## 4. Reported, Deciding Nothing

The result by position and by age; this season's rookies alone; the next season alone (FV1); today's values at 2026
week 9 for the top 25 and named players (Baker Mayfield, Daniel Jones, Bo Nix, Jared Goff).

## 5. Prior Looks — Full Disclosure

- `PREREG-in-season-comps.md` (same snapshots, outcome = starter seasons in years 1–3): counting the season so far was
  7–13% better at weeks 5, 9 and 13 on 2005–2022 (Brier), but its odds leaned high. That's a different outcome, but it
  tells us the direction.
- 2026 weeks 1–7 were looked at for five QBs (Baker QB30, Daniel Jones QB32, Bo Nix QB26, Goff QB2, Allen QB1).
- No in-season Own Value Scale prediction has been compared with any outcome.

## 6. Crash Tests, Before Lock

As `PREREG-ovs-era.md` §5, at week 9: noise world (≤ 1 of 20 passes), planted world w = 0.75 (≥ 80% of 200), w = 0.6
reported; leak checks asserted (pool `≤ Y − 5` at the same week, no self-match, both versions on identical rows).

## 7. Limits, Stated Now

- The value updates by week; it doesn't react to news between games.
- Weeks 1–4 stay on full seasons by design (too few games).
- Mid-season, five seasons ahead is the same outcome the offseason value uses; the rest of this season isn't priced.

## 8. Not Licensed Here

The DELTA Score, the site's model value, buy/sell calls. Nothing on the site changes.

## 9. Amendments

**Before lock**
- **A1 (8 Nov, Steve):** three seasons ahead, era-adjusted production, pool `≤ Y − 4`, test seasons 2013–2022 (§1–§2).
- **Crash tests (8 Nov, week 9, `study/out/ovs_in_season_crash.json`, 1,000 permutations):** noise world **0 of 20**
  (bar ≤ 1); planted w = 0.75 **200 of 200** (bar 80%), typical lift 5.2%; w = 0.6: 16 of 50, typical lift 1.5%.
  **PASS.** Leak checks asserted. Outcome identical to the era study's on all 10,604 shared rows.
