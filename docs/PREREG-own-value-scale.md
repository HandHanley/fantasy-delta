# PRE-REGISTRATION — DELTA's Own Value Scale (No Market Anywhere)

**Drafted:** 7 November 2026, before any result exists. **Status: LOCKED (see lock commit below).**
Locked by committing this document with `study/own_value_scale.py` and `study/test_own_value_scale.py` before the
confirmatory run. **Lock commit: `63c80df`.** Any change after that is an amendment (§12), never a silent edit.

---

## Plain-English Summary (For Steve)

**The idea.** Give every player a value on a 0–10,000 ruler that DELTA works out entirely by itself. Look at the 30 past
players most like him (the same matching Historical Comps already uses), see how many points above a replacement
starter each one scored over the next five seasons, flops counted as zero, and average them, with more recent players
counting more. The best player in a season is 10,000 and everyone else sits in proportion. FantasyCalc's numbers are
never read.

**The test.** Replay every offseason from 2013 to 2020 using only what was known at the time:
1. **Players:** is DELTA's value closer to what players actually went on to score than the simpler "players with the
   same scoring and age" average?
2. **Trades:** build thousands of realistic trades (one-for-one and two-for-one) between those players. Does DELTA's
   value pick the side that really ended up producing more, more often than the simpler method?

**What you get back.** Yes or no on both, how often each method called the trade right, and what today's players look
like on the new ruler.

---

## 1. What This Tests, And What It Doesn't

**Tests:** whether the Own Value Scale ("OVS", defined in §5) predicts players' next five seasons of fantasy value
better than production plus age (B2), and whether it calls trades between those players correctly more often.

**Does not test, and does not license changing:** the DELTA Score, projections, model value, buy and sell calls, the
accuracy ledger, or draft-pick values (a follow-up, §11). **No market data of any kind is read** (FantasyCalc's terms bar
using its data or "derivatives" to build a substitute for its trade calculator). Nothing on the site changes. Product use
needs Steve's approval after the results.

## 2. Prior Looks At The Data — Full Disclosure

- **1 Nov, `docs/PREREG-comparables-value.md` (locked `c3f2428`).** The original comparables value beat B2 by 5.7% on
  this same outcome (FV5) and test years (2013–2020), and by 7.2% for career years 0–2. **So Q1 below is largely
  expected to pass.** What's new here is the recipe actually adopted since (Version A matching, Fix 2 weights) and the
  trade question, which has never been run.
- **2 Nov, `docs/PREREG-draft-drop.md` (locked `e363bc1`).** Version A matching was 0.4% more accurate than the 1 Nov
  matching on FV5, 2013–2020 (not clearly real).
- **2 Nov, `docs/PREREG-honest-odds.md`.** Fix 2 weighting (recent comparables count more, halving every 8 seasons) was
  chosen for the three-year odds. It has never been tested on value (FV5).
- **1 Nov, chat.** A points-only Trade Calc mock (projected points carried forward) gave young unproven players almost no
  value; Steve ruled it out for dynasty. And four current players' comparables were looked at by hand.
- **7 Nov, this draft.** No outcome was compared with any prediction before the crash tests in §9.

## 3. Data

Same as the comparables studies: nflverse `player_stats_season.csv` (1999–2024, regular season),
`stats_player_reg_2025.csv`, `draft_picks.csv`, `players.csv`, and per-season `roster_YYYY.csv` positions (amendments
A11 and A12 of the 1 Nov study: non-skill labels fall back to the stats position, FB counts as RB). Half PPR plus TE
premium. Credit nflverse in anything published.

## 4. Snapshots And Outcome

Exactly the 1 Nov definitions, unchanged:
- **Snapshots:** veterans (≥ 1 game in season `t`) and incoming rookies (drafted after season `t`), QB/RB/WR/TE,
  features known at the end of `t` only.
- **FV5:** `Σ 0.9^(k−1) × max(0, P_(t+k) − R_(pos, t+k))` over the next five seasons. Replacement lines QB 24, RB 30,
  WR 42, TE 14 (12-team superflex). A missed season counts as zero.
- **Test seasons:** `t` = 2013–2020. **Time rule:** the pool for season `t` is snapshots from 2001 to `t − 5`.

## 5. The Methods

**OVS, the candidate.** For each test snapshot:
1. Its 30 nearest pool snapshots under **Version A** matching (`study/comps_draft_drop.py`, mode `'A'`): the 1 Nov
   weights, with draft slot set to zero for veterans in career year 2 or later. Rookies are matched on draft pick and
   age.
2. **Fix 2 weights:** each comparable counts `0.5 ^ ((t − s) / 8)`, where `s` is its season. Weights are normalised to
   sum to 1.
3. **Value** = the weighted average of the 30 comparables' FV5.
4. **The ruler (display only):** 10,000 × value ÷ the highest value among that season's snapshots. Scaling a whole
   season by one number changes no answer below.

Not tuned. Every constant comes from an earlier locked study.

**B2, the baseline:** production plus age bands, exactly the 1 Nov method (§6 of that study).

**Reported only:** B1, B3 and the 1 Nov comparables value (`CV`), so the change from the old recipe is visible.

## 6. Q1 — Players

On all test snapshots, is OVS's RMSE on FV5 at least **2% smaller** than B2's? Paired permutation test, 10,000 shuffles,
swapping the two methods' predictions for **all of a player's snapshots together**, one-sided. **p < 0.025** (two
deciding questions, lesson 7).

## 7. Q2 — Trades

**Building the trades (fixed before any outcome is read; seed 2026).** For each test season `t`:
- **Who can be traded:** the 240 test snapshots with the highest average of the two methods' predictions,
  `a = (OVS + B2) / 2`. Averaging the two keeps the selection fair to both.
- **1,500 one-for-one trades:** pairs drawn at random from all pairs whose `a` values are within 1.5× of each other.
- **1,500 two-for-one trades:** one player against two, both of them smaller than him by `a`, with the pair's total
  within 1.5× of the single player.
- **The truth:** the side whose players' FV5 adds up to more. A trade whose two sides came out exactly equal (usually
  both zero) has no winner and is dropped, counted.
- **A method's call:** the side its predictions add up to more on. A tie in predictions counts half right.

**The question.** Over all kept trades, is OVS's share of correct calls at least **2.0 percentage points higher** than
B2's? Permutation test as in Q1: for each player, swap which method's predictions he carries in every trade he appears
in, 10,000 times, one-sided, **p < 0.025**.

**Reported, deciding nothing:**
- One-for-one and two-for-one trades separately.
- **Young against old:** trades with a player in career years 0–2 on one side and only players in career year 5+ on the
  other. This is the case the points-only mock got wrong.
- Rookies (R0) in the trade, and by position.
- **How sure each call should sound:** for OVS, the share of trades won by the bigger side when it says that side is
  1.00–1.10×, 1.10–1.25× and 1.25–1.50× bigger. This would set the wording on a future calculator (Close / Clear).

## 8. Also Reported

- Counts at every step, every exclusion with its reason.
- RMSE, MAE and rank agreement for OVS, B1, B2, B3 and CV: overall, by position, and by career year.
- **Today's players on the ruler:** using every snapshot through 2020 as the pool (futures known through 2025), the 2025
  snapshots (veterans after the 2025 season, and 2026 rookies) on the 0–10,000 scale. Shown: the top 25, plus Marvin
  Harrison Jr., Makai Lemon, CeeDee Lamb, Javonte Williams, Caleb Williams, Brock Bowers and the nine players in Steve's
  12 Aug 2026 trade. Display only, produced after Q1 and Q2. These won't include anything from the 2026 season, which is
  still in progress.

## 9. Crash Tests, Before Lock

Run the real pipeline on synthetic outcomes. Record every result in §12 before locking.

1. **Noise world:** shuffle FV5 among snapshots of the same position and season, pool and test alike, so no method can
   know anything. OVS must pass Q1 or Q2 in **at most 1 of 20 runs**.
2. **Planted world** (as amended pre-lock, A1): for test snapshots, truth = `max(0, B2 + w × (OVS − B2) + e)`, where
   `e` is drawn from the real leftover errors around B2 (shuffled within position). `w` is how far the truth sits from
   B2 toward OVS. At **w = 0.75** OVS should pass **both** Q1 and Q2 in at least **80% of 200 runs**. A smaller edge,
   w = 0.6, is reported only. If the 80% bar is missed, the study is too small to see an edge that size, and Steve hears
   that before any real result.
3. **Leak checks (asserted in code):** every comparable is from season ≤ `t − 5`; no player is his own comparable; trade
   building reads no outcome; the OVS neighbours match `comps_draft_drop.neighbours(..., 'A')` row for row.

Real outcomes enter the crash tests only through the size of B2's leftover errors. No OVS prediction is compared with a
real outcome before the lock.

## 10. What Each Result Allows (Each Still Needs Steve's OK)

| Result | What It Means | What It Allows |
|---|---|---|
| Q1 and Q2 pass | DELTA's own value predicts players and calls trades better than the simpler method | OVS can become the Trade Calc's value. Picks first need the §11 follow-up |
| Q1 passes, Q2 doesn't | Better on players, no better at trades | Not for the Trade Calc. Reported as such |
| Q2 passes, Q1 doesn't | Calls trades better without predicting players better | Reported. A new pre-registration before any use |
| Neither | No gain | A documented null in `study/STUDIES.md` |

**Not tested here, and stated as such:** whether OVS is as good as the market. That comparison was too small to answer on
2 Nov (`claude/PREREG-comps-vs-market.md`).

## 11. Follow-Ups Not Licensed Here

- **Draft picks on the ruler:** a rookie-draft pick's value from the incoming rookies drafted in its range, using the
  Future Firsts study's rookie-draft order. Its own pre-registration.
- **Other league formats:** the replacement lines change with team count, superflex and scoring.
- **In-season updates.**

## 12. Amendments

### Pre-lock (7 Nov 2026)

- **A1. The planted world was a dead heat.** The draft's truth, `0.5 × OVS + 0.5 × B2 + e`, sits exactly halfway between
  the two methods, so neither can win on average. The first smoke run showed it (Q1 lift −0.04% at "w = 0.5"). Replaced
  by `B2 + w × (OVS − B2) + e` with w = 0.75 deciding power and w = 0.6 reported. Found on an 8-run smoke test; no real
  outcome was compared with an OVS prediction.
- **A2. Counted before any outcome was read:** 5,125 test snapshots (4,493 veterans, 632 incoming rookies) from 1,643
  players, none excluded for too few comparables. Trades built: 12,000 one-for-one and 12,000 two-for-one (1,500 of
  each in each of the eight seasons), before dropping ties.
- **A3. Smoke-run note.** In the noise world B2 called trades about 4 points better than OVS. That is expected: with
  outcomes shuffled within position, only position averages remain, and B2's larger bands estimate those more steadily
  than 30 comparables. It works against OVS, not for it.

### Pre-lock crash-test results (7 Nov 2026) — PASSED

| Synthetic World | Runs | Passed Q1 (Players) | Passed Q2 (Trades) | Middle Result |
|---|---|---|---|---|
| Noise: nobody can know anything | 20 | 0 | 0 | Players −0.8%, trades −1.5 points (OVS slightly worse, as A3 expects) |
| Planted, w = 0.75 (deciding) | 200 | 200 | 200 | Players +4.0%, trades +14.3 points: **both passed 100% (bar 80%)** |
| Planted, w = 0.6 (reported only) | 50 | 15 | 50 | Players +1.6%, trades +7.0 points |

Reading: no false passes on noise; ample power at w = 0.75. A small edge shows up in trade calls well before it clears
the 2% bar on players, so the trade question is the more sensitive one. Permutations here used 1,000 shuffles; the
confirmatory run uses 10,000. Saved: `study/out/own_value_scale_crash.json`.

## 13. Results (Confirmatory Run, 7 Nov 2026, Once, After Lock `63c80df`)

**Q1 — Players: PASS.** 5,125 test snapshots from 1,643 players. Typical miss (RMSE, FV5 points):
OVS 72.4 vs B2 77.2, **6.2% smaller**, p < 0.001 (no shuffle of 10,000 matched it).

**Q2 — Trades: PASS.** 19,075 trades kept (4,925 dropped because both sides produced exactly the
same, usually nothing). OVS called **59.9%** right, B2 47.5%: **+12.4 points**, p < 0.001.

**How to read the trade rates.** Trades were picked to be close on the average of the two methods, so wherever the two
disagree one must be right and the other wrong. That pushes the two rates apart and can leave the weaker method below
50%. The selection treats both methods the same (in the noise world B2 came out ahead), so the gap is the fair measure;
the absolute rates describe these hand-picked close trades, not trades in general.

| Trades | Kept | OVS Right | B2 Right |
|---|---|---|---|
| One-for-one | 8,349 | 59.6% | 47.0% |
| Two-for-one | 10,726 | 60.1% | 47.9% |
| Young (years 0–2) vs old (year 5+) | 5,522 | 59.3% | 47.9% |
| With an incoming rookie | 5,950 | 62.2% | 41.9% |

**How sure a call should sound (OVS):**

| OVS Says The Bigger Side Is | Trades | Bigger Side Actually Produced More |
|---|---|---|
| 1.00–1.10× bigger | 3,606 | 50% |
| 1.10–1.25× bigger | 4,442 | 56% |
| 1.25–1.50× bigger | 4,867 | 60% |
| 1.50×+ bigger | 6,160 | 69% |

Under 10% apart is a coin flip; the calculator should call those even.

**By group (RMSE, lower is better):** QB OVS 123.2 vs B2 131.6; RB 64.9 vs 70.8; WR 63.4 vs
66.2; TE 49.8 vs 52.6. OVS beat B2 at every position and every career year. **Incoming rookies:** draft-slot
bands (B3) still beat OVS (84.3 vs 87.4), as on 1 Nov; the picks follow-up (§11) should start from that.
The 1 Nov recipe (CV) scored 73.2: the adopted recipe is a little better (72.4).

**Today's players** (snapshots after the 2025 season, nothing from 2026): see `study/out/own_value_scale_results.json`,
`current_players`. The 12-team superflex lines put quarterbacks at the top (Allen 10,000, Lamar 9,984).

**Verdict (§10 row 1):** OVS can become the Trade Calc's value, with Steve's OK, once picks (§11) are valued.

