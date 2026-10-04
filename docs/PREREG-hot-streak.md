# PRE-REGISTRATION — Sell The Hot Streak? What Happens To A Player's Price After Three Big Weeks

**Written:** 4 October 2026. No outcome has been looked at: the only runs were `--count` (streaks, groups, names,
snapshot dates and each player's price rank *before* his streak — no price after a streak is read) and crash tests
in which every later price was replaced by random numbers (they prove the code runs and the tests are fair —
nothing more).
**Status:** locks on commit. Changes after the first run go in Amendments, with a reason.
**Script:** `scripts/hot-streak-study.py` — `--count`, `--crash`, then `--run`, which refuses unless this file is
committed and unedited.
**What kind of study:** content for the newsletter. **It changes nothing in the engine** and needs no ship gate.

---

## 1. The Question

A player nobody priced as a starter has three straight starter-level weeks. His dynasty price jumps. Classic advice
says **sell into the hype — the price will fall back.** Does it? **After the streak, does his price fall further than
players who were priced the same at that moment?** Checked twice: when the season ends, and the next preseason.

---

## 2. The Streak — Defined Before Any Price Is Read

- **Starter-level week:** top 12 at QB or TE, top 24 at RB or WR, that week, in DELTA's scoring (`bt_pts`: half-PPR,
  TE +1 a catch).
- **The streak:** three of **his** games in a row (byes and missed weeks skipped), all starter-level, the third in
  **Weeks 3–14**. First streak per player-season. **Seasons 2021–2025** (2020 has no December or January price
  snapshots).
- **Unexpected:** in the last price snapshot before his first streak game, he was priced **outside that same starter
  line** (outside the top 12 QB/TE, top 24 RB/WR) — a player priced as a bench player who played like a starter.
- **179 streaks from 142 players** — QB 37 · RB 63 · WR 53 · TE 26; 31–40 a season. e.g. 2024: Nick Westbrook-Ikhine
  (WR149), Cedric Tillman (WR97), Kareem Hunt (RB82), Darnell Mooney (WR64), Jerry Jeudy (WR58), Rico Dowdle (RB51).

**Changed before lock, on counts alone:** the first draft used "top 12 at every position". It kept 85 streaks — only
6 WRs and 16 RBs, 37 QBs — so the study would have been mostly about quarterbacks, when the reader's question is the
waiver-wire receiver or back. The starter-level line keeps 179, balanced across positions.

---

## 3. Prices

- DynastyProcess `files/values.csv` git history, `value_2qb` (superflex). ⚠ **Expert rankings, not trade prices.**
  `L(v) = log(v + 100)`; a player who falls out of the rankings counts as 0.
- **After the streak:** the first snapshot after his third game's week ends (within 10 days; actual: 4 days, every
  case). **Before:** the last snapshot before his first streak game's week starts (actual: 6 days).
- **Season over:** the snapshot nearest **15 January**; **next preseason:** nearest **15 August** (within 14 days allowed;
  every season has both, all within 3 days of the 15th — 14 Jan 2022 through 14 Aug 2026).

---

## 4. The Comparison And The Tests

- **His move:** `d = L(price at the horizon) − L(price right after the streak)`.
- **The comparison:** every player priced in that same after-streak snapshot, overall rank 400 or better, **with no
  streak of any kind that season.** For each snapshot, a line is fitted through them:
  **move ~ price right after + Rookie + Second-Year + Aging.**
  - **Why the three extra terms:** today's Price Calendar (`PREREG-price-calendar.md`) showed rookies gain 20–28% on
    equally priced veterans between October and January, and aging veterans fall. Streak players include 20 rookies,
    25 second-year players and 48 aging veterans (RB 26+, WR 29+, QB 32+). Without the terms, a rookie streaker would
    look like he "held his value" just for being a rookie. Draft year: nflverse, then DynastyProcess's own (which
    covers undrafted players); age on 1 September.
- **His gap** = his move minus what the line predicts for him.
- **Two tests:** **Season over** and **Next preseason.** A test is **SHOWN** only if all three hold:
  1. **Size:** the average gap is at least **3%** either way. (3%, not the calendar's 5%: streak players are cheap by
     design, and `L` shrinks moves on cheap players most — a planted −15% reads about −5%.)
  2. **Not a fluke:** its **97.5%** range excludes zero — 4,000 resamples of the streak **players** (some streak in
     more than one season) **and** of each snapshot's comparison pool, refitting its line each time. Seed 20261005.
     97.5% because there are two tests.
  3. **Holds in both halves:** 2021–2023 and 2024–2025 point the same way.
- **Negative and SHOWN = "sell the streak" supported. Positive and SHOWN = the price kept rising — hold.**

**Reported only:** the price jump during the streak; results by position, by group (Rookie / Second-Year / Aging /
Other) and by season; **points per game before, during and after the streak, and the next season** — did the
production last?; the biggest give-backs and the biggest further gains.

---

## 5. Honest Limits

- **It can confirm a give-back of roughly 12–15% or more.** Planted −12% at season end read −5.0% and was SHOWN; planted
  −15% at the next preseason read −4.8% and was SHOWN. A real give-back of under ~10% will likely read "not shown".
- **Rankings, not trades.** Rankers may adjust more slowly than traders, which could hide a spike-and-fall that real
  trades show.
- **Five seasons, 179 streaks;** by-position results are thin (TE 26) and reported only.

---

## 6. Prior Work — Full Disclosure

- **Market-Form (`PREREG-market-form.md`, 26 Sep): not shown.** DELTA's in-season form read did not predict price changes
  from Weeks 4 and 8 to the next preseason, against players priced the same. A hot streak is an extreme form signal,
  so that null is the main reason for the prediction below.
- **Price Calendar (4 Oct):** used here for the Rookie / Second-Year / Aging terms (§4).
- **Rookie Sell-High (29 Sep):** selling *full-season* rookie breakouts was a coin flip — a different event (a season,
  not three weeks).
- **Seen before locking:** streak counts by season and position under four candidate definitions; names, weeks and
  pre-streak price ranks; snapshot dates and lags; crash-test output on random prices; a contrast run (§ Pre-Lock).

---

## 7. Stated In Advance, So It Can Be Wrong

- **Season over:** not shown.
- **Next preseason:** slightly negative — some give-back — but **not shown**.

---

## 8. What It Could Lead To

A newsletter article — working title **"Sell The Hot Streak?"** — with the price result and the "did the points last?"
picture side by side. **No engine change.**

---

## Pre-Lock Checks (4 October 2026)

| Check | Result |
|---|---|
| Streaks (first per player-season, 2021–25) | 391 found · 211 not cheap · 1 unpriced · **179 kept** from 142 players |
| Snapshot lags | Before: 6 days · after: 4 days · every season has both horizons |
| Missing draft year | 21 at first (undrafted players — nflverse lists only drafted ones) → **0** after adding DynastyProcess's draft year as a fallback |
| Noise runs (3) | 0 of 6 SHOWN; every range included zero |
| Planted give-backs | −15% next preseason → that test only SHOWN (−4.8%) · −12% season end → that test only SHOWN (−5.0%) |
| Every rookie +25%, pool included | Absorbed by the line: streak gap **+0.0%**, not shown |
| Contrast — the same rookie plant with the three terms switched off | −2.0% vs −0.9% with them on: rookies are a similar share of streak players and pool here, so the terms change little **in this sample** — kept because nothing guaranteed that balance in advance |
| `--run` refuses while this file is uncommitted | Refused |

---

## Amendments

*(none)*

---

## Result (4 October 2026) — Don't Sell The Streak: Prices Kept Climbing (And A Flaw Found After The Run)

Run once, `python3 scripts/hot-streak-study.py --run`, against this file as committed in `e57f579`
(sha256 prefix `0483a95bad454f71`, printed by the run). Nothing above this section was changed after the run.
Full output, including the check below: `study/out/report_hot_streak.txt`.

### As Locked

| Test | Gap vs Players Priced The Same | 97.5% Range | Halves (2021–23 / 2024–25) | Verdict |
|---|---|---|---|---|
| **Season over** (mid-Jan) | **+38.6%** | +27.5% to +50.4% | +33.3% / +48.6% | **SHOWN — positive** |
| **Next preseason** (mid-Aug) | **+51.6%** | +34.8% to +71.4% | +50.5% / +53.7% | **SHOWN — positive** |

**Prediction (§7): wrong, and in direction.** I predicted nothing at season's end and a small give-back by preseason.
Instead the streak players' prices kept **rising** against players priced the same — "hold", not "sell" (§4).

### A Flaw In The Comparison, Found After The Run — Corrected Numbers Below Are NOT Pre-Registered

**What was wrong.** §4's pool dropped every player with a streak **at any point that season** — including streaks
that came *after* the comparison date. A player priced the same in Week 5 who went on a run in Weeks 9–11 was thrown
out of the pool for something that had not happened yet, so the pool leaned toward players who did nothing for the
rest of the year. The crash tests could not catch this: their random prices ignored who streaked.

**The check.** `scripts/hot-streak-lookahead-check.py` reruns the locked script with that one rule changed. It
reproduces the locked numbers exactly first, then:

| Pool | Season Over | Next Preseason | Verdict Under §4's Rules |
|---|---|---|---|
| As locked (excludes any streak, any time) | +38.6% | +51.6% | SHOWN / SHOWN |
| **Fixed: excludes only streaks already over by that date** | **+29.2%** (+19.1% to +39.5%) | **+35.3%** (+20.3% to +51.9%) | SHOWN / SHOWN |
| Excludes only the 179 streak players | +30.3% (+20.1% to +41.4%) | +28.7% (+14.8% to +44.8%) | SHOWN / SHOWN |

**The flaw inflated the result by about 9–16 points (locked vs fixed); the conclusion survives every version.** The article should
use the **fixed** numbers — about **+30% by season's end, +30–35% by the next preseason** — and say how they were
arrived at.

### What It Says, Plainly

- **The market under-reacts to a hot streak, it doesn't over-react.** The price jumped during the streak (median
  +31%, raw) and then kept climbing against equally priced players for months. Selling right after the third game
  sold early, on average.
- **The points mostly lasted.** Points per game before · during · rest of season · next season (reported only):
  QB 14.3 · 23.2 · 17.1 · 15.5 — RB 7.3 · 16.7 · 11.0 · 9.4 — WR 8.6 · 17.4 · 10.5 · 9.4 — TE 7.1 · 15.6 · 10.0 · 9.4.
  The streak itself was not repeatable, but the player kept scoring well above where he was before it.
- **Every season, every position, every group pointed the same way** (as locked, reported only; season over):
  QB +48.6% · RB +37.4% · WR +31.6% · TE +42.8%; Rookies +47.1% · Second-Year +52.4% · Aging +36.9% · Other +34.0%;
  2022 the weakest year (+24.6%), 2024 the strongest (+62.9%).
- **Averages hide busts.** Biggest give-backs by the next preseason: James Robinson 2022, Clyde Edwards-Helaire 2022,
  Zack Moss 2021, Desmond Ridder 2023, Alexander Mattison 2023 (−64% to −80%). Biggest gains: Bucky Irving 2024,
  Chase Brown 2024, Dalton Schultz 2021, Geno Smith 2022, Josh Jacobs 2022. (Locked-pool figures.)

### Limits, Restated

- **Rankings, not trades.** Expert rankings may simply update slowly; part of the "kept climbing" could be rankers
  catching up rather than the trade market rising. The Calendar Forward Check (FantasyCalc trades, `STUDIES.md`)
  could test this from 2026 on.
- The fixed numbers are an after-the-run correction. They answer "how much did the flaw matter", not a fresh test.

### Method Lesson

**Every filter on a comparison group must use only what was known on the comparison date.** Excluding a player for
something he did later quietly picks the pool by its future. Check every exclusion rule for this before lock.

**What it leads to:** the newsletter article (§8), with the flaw disclosed. No engine change.
