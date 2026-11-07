# DELTA Studies — Index And Newsletter Plan

**Started 3 October 2026.** One place to see every study DELTA has run, what it found, and which ones would make a
good newsletter piece. The full record for each lives where it always has: `docs/PREREG-*.md`, `docs/RESEARCH-*.md`
and handoff §6. ⚠ Handoff §6 cites `NULL-RESULTS.md` for the August nulls; **that file is not in the repo**
(checked 3 Oct) — their scripts are in this folder. **Before writing an article from any row, re-read its source file** — this index is a summary and
summaries lose caveats.

Newsletter fit: **Strong** (write it) · **Possible** (worth a look) · **Skip** (too technical, or off-brand).

---

## 1. Studies That Changed The Model

| Study | What We Found, In Plain Terms | Verdict | Newsletter Fit | Source |
|---|---|---|---|---|
| Rookie Draft-Capital Baseline | Where a rookie was drafted is the best starting guess for his first year — 30% smaller misses | Shipped | Good | Handoff §4 |
| Play-Caller Portability | A play-caller who moves teams brings about half his offense's fingerprint | Shipped | **Strong** (pair with next) | §6 |
| Coordinator-Change Penalty | A new coordinator *title* doesn't hurt players — 1,388 cases, no effect | Ruled out | **Strong** | §6 |
| Projection Age Curve | Age explains at most about 1% of next year's points — real but small | Shipped (deliberately under the bar) | Good | §6 |
| Team Changers (four studies) | Players who switch teams score ~17% below their own history, at every age, stars included | Shipped (×0.898) | **Strong** | `PREREG-team-change*.md` |
| QB Points Per Start | Judge a QB on games he starts; thin-history QBs need ~13 starts before their own number is trusted | Shipped | Possible | `PREREG-qb-perstart.md` |
| QB Starter Lift × Missed Time | A technical fix to how two QB adjustments combine | Shipped | Skip | `PREREG-qb-missedtime.md` |
| In-Season Blend (Veterans, Rookies) | How many games before this season counts more than last; rookies are trusted sooner | Shipped | Possible ("When Is A Hot Start Real?") | `PREREG-in-season-blend*.md` |
| Missed-Time Penalty Sizes | Sizing the cuts for missed games | Shipped | Skip (availability topic) | `PREREG-missed-time.md` |
| Undrafted Rookie Baseline | An undrafted rookie's typical first year is tiny — a WR averages under 1 point a game | Shipped | Possible | `PREREG-rookie-baseline-v2.md` |
| RB Dominator Weight | College backs who catch passes were undersold; counting receiving yards fixes it | Shipped | Possible (devy readers) | `PREREG-rb-dominator-weight.md` |

## 2. Durable Findings

| Study | What We Found | Verdict | Newsletter Fit | Source |
|---|---|---|---|---|
| Aging Is Availability | Older players don't score less per game — they disappear. Rate holds near 1.0; survival falls 85% → 60% | Finding | **Strong** — maybe the best one | §6 |
| Draft Capital → Breakout Odds | Ever startable: top-10 WR 71%, Round 2 WR 43%, Day 3 WR 7%. Peaks in year 2–3, never year 1 | Finding | **Strong** | §6 |
| Median, Not Mean, For Late Rookies | 88 late-round WRs: 36% under 2 PPG, 6% startable, the top five carry 18% of the points | Modelling stance | **Strong** | §6 |
| QB Misses Are Role Changes | DELTA's QB misses come from not knowing who starts; WRs show no such effect | Finding | Good | §6 |
| Rookie QB Threat | A starter whose team drafts a top-64 QB loses the job 52% of the time (18% otherwise); 67% behind a top-10 pick | Finding, queued | **Strong** | §6 |
| K = 24 | About 1.5 seasons before a young player's production outweighs his draft slot | Finding, queued | Good | §6 |
| 2025 Backtest | Projections missed by about 1.2 points a game; 78% landed within 2 | Validation | Good | §6 |
| Scarcity Validation | League-size adjustments match the market in 29 of 32 cases | Validation | Skip | §6 |

## 3. Tested And Didn't Pass

| Study | What We Found | Verdict | Newsletter Fit | Source |
|---|---|---|---|---|
| Can We Beat The Market? | A market-free value lost to consensus every year, at every horizon; blending it in made the market worse | Rejected | **Strong** | `RESEARCH-market-independent-value.md` |
| DELTA's In-Season Form vs Price Moves | DELTA's in-season read doesn't predict where prices go | Not shown | Fold into the above | `PREREG-market-form.md` |
| Boom-Bust Penalty | Raw volatility *hurts* predictions; how often a player busts helps a little, not enough to ship | Failed | **Strong** | §6 |
| Sell Your Breakout Rookie? | Selling breakouts was a coin flip — 51% lost value | Not supported | **Strong** (pair with next three) | `PREREG-rookie-sellhigh.md` |
| Which Breakouts Fade? | ~8% sophomore slump in every sample; no trait picks who fades | No trait confirmed | Fold in | `PREREG-rookie-breakout.md` |
| High-Volume Rookies Fade More? | Not confirmed on fresh classes | Not confirmed | Fold in | `PREREG-rookie-volume.md` |
| Pedigree Gap | The market prices draft slot about right after year one | Priced right | Fold in | `PREREG-pedigree-gap.md` |
| College Production Beyond Draft Slot | College dominance adds almost nothing once draft slot is known | Not shown | Good | `PREREG-college-signal.md` |
| "He Came On Late" | Second-half rookie surges don't predict year two | Not shown | Good | `PREREG-rookie-trajectory.md` |
| Role-Entry Odds | Draft-slot odds work but run too confident at the top; pick-5 RB 68% (2000–14) vs 96% (2015–23) | Not shown | Possible | `PREREG-role-entry*.md` |
| Rookie Table Refit | Modern rookies far outscore old ones (QBs drafted 33–64: 5.2 → 12.2 PPG) | Failed | Good (the era shift is the story) | §6 |
| Usage vs Points Early In Season | Target and snap share don't beat plain points early on | Not shown | Possible | `PREREG-usage-blend.md` |
| QB TD% Regression | Small effect, below the bar | Null | Possible — re-read first | `study/td_pct_study.py`, `td_pct_round2.py` |
| Goal-Line Work | Made predictions worse | Null | Possible — re-read first | `study/gl_opportunity_study.py` |
| Season Weights · Start Profile Penalty · Smooth Draft Curve · Mid-Season Trades | Today's rules held | Not shown | Skip | `PREREG-*.md` |
| Scheme Change · Style Terciles | Too little data; re-run around 2029 | Deferred | Skip | §6 |

## 4. Still Running

| Study | What It Will Show | When |
|---|---|---|
| Accuracy Ledger | DELTA's frozen preseason calls graded against what happened — the flagship article | February 2027 |

---

## 5. Newsletter — The Five To Write First

1. **"Old Players Don't Slow Down. They Disappear."** — Aging Is Availability.
2. **"We Tried To Beat The Market. Here's Why We Lost."** — the market-independent value study.
3. **"Should You Sell Your Breakout Rookie?"** — the coin flip, plus the 8% sophomore slump.
4. **"The Hidden Cost Of A New Jersey."** — the 17% team-change gap.
5. **"Follow The Play-Caller, Not The Title."** — portability and the coordinator null together.

---

## 6. New Studies For The Newsletter

Content studies change nothing in the engine and need no ship gate, but each is **pre-registered** and published as
found, misses included. Checked against the record before listing (method lesson 12).

| Study | The Question | Status |
|---|---|---|
| **The Price Calendar** | When in the dynasty year is each kind of player dearest, against a player priced the same? | **Ran 4 Oct.** Summer: nothing moves. Rookies gain on equally priced veterans from October (+20% Nov, +33% Apr). Aging veterans drop: RB 26+ and QB 32+ in October, WR 29+ in December (−15% to −22% by Jan–Apr). Second-Year and QB 32+ not shown. **Newsletter: Strong.** `docs/PREREG-price-calendar.md` · `study/out/report_price_calendar.txt` |
| **Sell The Hot Streak?** | After three starter-level weeks from a player priced as a bench player, does his price fall back further than players priced the same? | **Ran 4 Oct — SHOWN, the opposite way: don't sell.** Prices kept climbing ~+30% vs equally priced players by Jan and by next preseason (after fixing a look-ahead flaw found post-run; locked run said +39% / +52%). Points mostly lasted. **Newsletter: Strong.** `docs/PREREG-hot-streak.md` · `study/out/report_hot_streak.txt` |
| A Receiver's QB Change | When a WR's quarterback changes, how much does his production move? | Idea. Doubles as the first test of the QB-quality adjustment |
| **What Is A Future First Worth?** | Is one early first (1.01–1.04) worth two late firsts (1.09–1.12), in starter-level seasons over years 1–3? | **Ran 4 Oct — not shown: about fair.** Early 1.60 vs Late 0.75 starter seasons (2.1×). The 1.01 stands apart (2.3, 10 of 10 hit). A future first: 1.12 starter seasons, 60% give at least one. **Newsletter: Strong.** `docs/PREREG-future-first.md` · `study/out/report_future_first.txt` |
| **Are Running QBs A Safer Bet?** | Does a runner keep more points, and more predictably, than a pocket QB who scored the same? | **Ran 4 Oct: not shown, not shown.** Runners kept +0.75 points per start (range crosses zero) and were no steadier. Rushing repeats more (0.81 vs 0.55), but mostly by arithmetic. "Pay for the points, not the legs." **Newsletter: Strong** (myth-check). `docs/PREREG-qb-rushing.md` · `study/out/report_qb_rushing.txt` |
| Do Easy Schedules Fool Us? | Do points against weak defenses carry into the next stretch? | Idea. nflverse data in hand |
| The Payday Dip | Do players produce less after a big second contract? | Idea. **Needs historical contracts** — not confirmed available |
| When Does Usage Become Real? | How many games until target share stops bouncing? | Already in backlog §8 (usage stabilisation) |
| Does Landing Spot Matter? | Beyond draft slot, does the offense a rookie joins change his odds? | Queued last on the 29 Sep outside review; never run |
| Calendar Forward Check | Does the price calendar hold in **real trades** (FantasyCalc, DELTA's own nightly archive since 19 Apr 2026) and in a season it never saw? Plus a 1QB version | Idea, **later (owner, 4 Oct)**. Completes May 2027. Disclose: a few current values were printed while checking the archive's structure |
| **Players Like Him (Comparables Value)** | Does valuing a player by what his 30 most similar past players went on to do beat simpler averages, and are its odds honest? | **Ran 1 Nov — more accurate, odds not honest.** Beat production + age (B2) by 5.7% overall and 7.2% for players in years 0–2 (both p < 0.001; same answer with corrected positions). Its "chance of a starter season" runs high in the middle (said 43%, happened 34%), honest only at RB. Draft-slot bands still beat it for incoming rookies. Nothing shipped; product use is Steve's call. **Newsletter: Strong** ("Players Like Him"). `docs/PREREG-comparables-value.md` (locked `c3f2428`) · `study/out/report_comps_value.txt` |
| **Honest Odds For Players Like Him** | Can the "chance of a starter season in the next three years" be made honest? | **Ran 2 Nov — yes, narrowly, with recent comparables counting more.** On 1,359 players never graded before (2021–22), weighting recent comparables more (halving every 8 seasons) was the only version judged honest; as-is and a league-size fix were not. Veterans still lean ~2.7 points high (19.8% said, 17.1% happened), within chance at this size. League-size scaling fixed veterans but sank rookies. **Second pass (2 Nov, 2009–12 players): honest again**; rookies read low in both tests (by 2 and 5 points). Fix 3 (league size for veterans only) too weak to test now. Re-check on the 2023 players in early 2027 (`docs/PREREG-honest-odds-v3.md`). **Newsletter: Possible** (pair with Players Like Him). `docs/PREREG-honest-odds.md` (locked `356f183`) · `study/out/honest_odds_results.json` |
| **Players Like Him: More Weight On Draft Slot?** | Should young veterans' matches lean on draft slot as much as the August K = 24 finding implies? | **Ran 2 Nov — no, keep today's weights.** Matches look more sensible (Bowers' range picks 6–42 instead of 6–113) but predictions got 1.2% worse for years 1–3 veterans and the odds lost their honest rating. `docs/PREREG-draft-weight.md` (locked `ee43651`). |
| **Players Like Him: Drop Draft Slot After Two Seasons?** | Once a player has two seasons of data, can matching ignore draft slot? | **Ran 2 Nov — yes.** Accuracy 0.4% better (not clearly real), odds still honest on fresh 2021–22. Adopted for the cards: the draft row shows only for players with under two seasons. `docs/PREREG-draft-drop.md` (locked `e363bc1`, crash fix `713b33b`). |
| **Players Like Him vs The Market** | Once you know the market price, does Players Like Him add anything? | **Not run — too small to answer (2 Nov).** Crash tests: a realistic edge passes the 2% bar only 4% of the time. Draft in the Project (`claude/PREREG-comps-vs-market.md`). Possible longer route: next-season ADP history. |
| **Historical Comps During The Season** | Mid-season, does matching on this season's play keep the odds honest? | **Ran 7 Nov — no, keep season-end matching.** More accurate at every week (Brier 8.5% better at week 9, 10% at week 13, p < 0.02; 7–13% better across 2005–22), but the odds ran high at all three weeks (said 17%, happened 14% on 2021–22) and failed the honesty rule by small margins. The baseline ran higher still. `docs/PREREG-in-season-comps.md` (locked `d03efe3`). |
| **In-Season Comps, Corrected For The Lean** | Can a time-safe correction (measured on past seasons only) make the in-season odds honest? | **Not run, 7 Nov: crash tests failed.** In a planted 16%-high world the correction got the average right but passed the honesty rule 30 of 40 times (bar 32; an honest forecaster passes ~34). Draft `docs/PREREG-in-season-comps-v2.md` (not locked). Next: correct by position, or wait for the 2023 players (early 2027). |
| The TE Year-3 Breakout | Do tight ends really break out later than receivers? | Idea. Partly covered by the breakout-odds study |

**Off the list on purpose:** anything that would measure or label injury-proneness.
