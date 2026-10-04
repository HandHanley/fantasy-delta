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
| **Sell The Hot Streak?** | After three starter-level weeks from a player priced as a bench player, does his price fall back further than players priced the same? | **Pre-registered 4 Oct** — `docs/PREREG-hot-streak.md`, `scripts/hot-streak-study.py`. Awaiting lock. 179 streaks, 2021–25 |
| A Receiver's QB Change | When a WR's quarterback changes, how much does his production move? | Idea. Doubles as the first test of the QB-quality adjustment |
| What Is A Future First Worth? | Is the 1.01 worth two late firsts, by breakout odds? | Idea. Builds on the breakout-odds study |
| **Are Running QBs A Safer Bet?** | Does a runner keep more points, and more predictably, than a pocket QB who scored the same? | **Ran 4 Oct: not shown, not shown.** Runners kept +0.75 points per start (range crosses zero) and were no steadier. Rushing repeats more (0.81 vs 0.55), but mostly by arithmetic. "Pay for the points, not the legs." **Newsletter: Strong** (myth-check). `docs/PREREG-qb-rushing.md` · `study/out/report_qb_rushing.txt` |
| Do Easy Schedules Fool Us? | Do points against weak defenses carry into the next stretch? | Idea. nflverse data in hand |
| The Payday Dip | Do players produce less after a big second contract? | Idea. **Needs historical contracts** — not confirmed available |
| When Does Usage Become Real? | How many games until target share stops bouncing? | Already in backlog §8 (usage stabilisation) |
| Does Landing Spot Matter? | Beyond draft slot, does the offense a rookie joins change his odds? | Queued last on the 29 Sep outside review; never run |
| Calendar Forward Check | Does the price calendar hold in **real trades** (FantasyCalc, DELTA's own nightly archive since 19 Apr 2026) and in a season it never saw? Plus a 1QB version | Idea, **later (owner, 4 Oct)**. Completes May 2027. Disclose: a few current values were printed while checking the archive's structure |
| The TE Year-3 Breakout | Do tight ends really break out later than receivers? | Idea. Partly covered by the breakout-odds study |

**Off the list on purpose:** anything that would measure or label injury-proneness.
