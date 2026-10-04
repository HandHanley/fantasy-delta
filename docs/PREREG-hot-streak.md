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
