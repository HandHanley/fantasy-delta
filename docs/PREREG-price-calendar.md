# PRE-REGISTRATION — The Price Calendar: When In The Dynasty Year Is Each Kind Of Player Dearest?

**Written:** 3 October 2026. No outcome has been looked at: the only runs were `--count` (snapshot dates and the
May starting groups — May prices are used only to pick the top 300 and are never printed) and crash tests with
every later price replaced by random numbers (they prove the code runs and the ranges are honest — nothing more).
**Status:** locks on commit. Changes after the first run go in Amendments, with a reason.
**Script:** `scripts/price-calendar-study.py` — `--count`, `--crash`, then `--run`, which refuses unless this file
is committed and unedited.
**What kind of study:** content for the newsletter. **It changes nothing in the engine** and needs no ship gate.
It is pre-registered anyway so that whatever it finds can be published as found.

---

## 1. The Question

Dynasty prices move through the year: the draft, training camp, the season, the playoffs, the offseason. **For
each kind of player, is there a month when he is reliably dearer or cheaper than a player who started the year at
the same price?** If so, that is a calendar a manager can trade on: sell the group in its strong month, buy it in
its weak one.

"Than a player who started at the same price" is the point. A trade swaps one player for another, so what matters
is how a rookie's price moves **against a veteran priced the same**, not against nothing.

---

## 2. The Data

- **Prices:** DynastyProcess `files/values.csv` git history, `value_2qb` (superflex, DELTA's anchor). ⚠ These are
  **expert consensus rankings turned into values** (FantasyPros ECR), not trade prices — the same limit as every
  DELTA market study. The article must say "rankings", not "trade prices".
- **Five cycles,** May 2021 → April 2022 through May 2025 → April 2026. The 2020 cycle is out (no December or January
  snapshot). Month 0 is May; month 11 is April.
- **Snapshot for a month:** the commit dated nearest the 15th, within 14 days. Chosen from commit dates only.
  2025–26 has no March or April snapshot, so April rests on four cycles.
- **Players** join by ID only: `fantasypros_id → gsis_id` through DynastyProcess's crosswalk; draft year from nflverse
  draft picks (DynastyProcess's own `draft_year` as fallback — it is blank for many rows); age from the crosswalk's
  birthdate, on 15 May.
- **A player missing from a snapshot that exists counts as price 0** (he dropped out of the rankings — that is part
  of the story, not missing data). `L(v) = log(v + 100)`, as in every DELTA market study.

---

## 3. The Groups — Fixed In May

The cohort is the **top 300 QB/RB/WR/TE by superflex value in the May snapshot.** Each is labelled once, in May, in
this order:

| Group | Who | Players, Pooled |
|---|---|---|
| **Rookie** | Drafted that spring | 275 |
| **Second-Year** | Drafted the spring before | 239 |
| **RB 26+** | RB, 26 or older on 15 May, drafted two or more springs earlier | 143 (70 different players) |
| **WR 29+** | WR, 29 or older, same | 79 (40) |
| **QB 32+** | QB, 32 or older, same — **small**: 6–13 a year | 43 (17) |
| *Comparison pool* | Everyone else (younger veterans and all TEs) | 705 |

---

## 4. The Measure And The Test

- **His move:** `d = L(price this month) − L(price in May)`.
- **His price-matched gap:** his move minus the comparison pool's straight line (move against May price), fitted
  separately for each cycle and month. This is the pedigree study's method, and for the same reason: prices drift
  back toward the middle on their own, so a plain "group vs everyone" gap reads noise as a pattern.
- **Four windows are graded:** **Aug** (preseason), **Nov** (midseason, trade deadline), **Jan** (season over),
  **Apr** (pre-draft). Five groups × four windows = **20 tests**.
- **A window is SHOWN only if all three hold:**
  1. **Size:** the average gap is at least **5%** either way.
  2. **Not a fluke:** its **99%** range (4,000 resamples, seed 20261003) excludes zero. 99%, not 95%, because there
     are 20 tests. Each resample redraws the group's **players** (a player can sit in a group in more than one cycle)
     **and** the comparison pool, refitting its line.
  3. **Repeats:** the same direction in at least 4 of the 5 cycles (all 4 of 4 for April).
- **A group "has a calendar"** if any of its four windows is SHOWN. Its strong and weak windows are then read off.
- **Reported only, no verdict:** the full month-by-month calendar; each group's **raw** price change from May (not
  price-matched — it includes the drift back to the middle and the drop-outs, and says so); the by-cycle numbers.

---

## 5. Honest Limits

- **Small swings will read "not shown".** The crash test planted a true 10% rookie rise: it read as +5% to +6%
  (`L` cushions cheaper players) and was SHOWN in one of its two windows, missed by a hair in the other. Read the
  study as able to find swings of **roughly 10–15% or more.**
- **WR 29+ and QB 32+ are small** (40 and 17 different players). For them, "not shown" mostly means "too few to tell".
- **Rankings, not trades** (§2). Five cycles, one market source.

---

## 6. Prior Work — Full Disclosure

- **Rookie Sell-High (`PREREG-rookie-sellhigh.md`, 29 Sep):** saw rookie price changes from the end of the rookie
  season to the end of year two — **other rookies fell about 11%** (not price-matched). That overlaps this study's
  Second-Year group, so a Second-Year decline is **not** a fresh finding here.
- **Pedigree Gap (29 Sep):** price changes for 2020–23 classes into year three. **Market-Form (26 Sep):** prices
  before Week 1, after Weeks 4 and 8, and the next preseason, 2020–25. **Market-independent value (Aug):**
  September snapshots 2019–24. None of these computed a price-matched calendar by group and month.
- **Seen before locking:** snapshot dates; group counts and the lowest-priced names in each 2024 group (to check the
  labels); crash-test output on random prices.

---

## 7. Stated In Advance, So It Can Be Wrong

- **Rookie:** dearer than veterans priced the same in **August** (camp hype); cheaper by **April** (the next class
  arrives).
- **Second-Year:** cheaper by **January and April** — but see §6, this is already half-seen.
- **RB 26+:** cheaper, widening through **November, January and April.**
- **WR 29+ and QB 32+:** not shown — too few.

---

## 8. What It Could Lead To

A newsletter article — working title **"The Dynasty Calendar: When To Buy And Sell Each Kind Of Player"** —
reporting every group and window as found, including the ones that are not shown. **No engine change.**

---

## Pre-Lock Checks (3 October 2026)

| Check | Result |
|---|---|
| Snapshots | Every May start within 11 days of the 15th; every graded window within 3 days; 2025–26 has no Mar/Apr |
| Groups (May only) | e.g. 2024 Rookie: Jaheim Bell, Cade Stover · RB 26+: Jerick McKinnon, Dalvin Cook · QB 32+: Russell Wilson, Derek Carr, Aaron Rodgers |
| Missing draft year or age in the top 300 | 0–1 per year (excluded) |
| **A flaw the crash test caught** | First version resampled only the group's players, holding the comparison line fixed. On random prices a 99% range excluded zero (Rookie, Nov, −4.4%, all five cycles) — the line's wobble moves a whole cycle's group together. Fixed: each resample redraws the pool and refits the line. After: **1 of 60** ranges excluded zero on three random-price runs, 0 SHOWN |
| Planted effects | Rookies +10% Aug–Nov → Aug SHOWN (+6.4%), Nov +5.0% just under the size bar; RB 26+ −15% from Nov → Nov, Jan, Apr all SHOWN (−8% to −11%), nothing else |
| `--run` refuses while this file is uncommitted | Refused |

---

## Amendments

*(none)*

---

## Result (4 October 2026) — Rookies Gain, Aging Veterans Fall Off A Mid-Season Cliff

Run once, `python3 scripts/price-calendar-study.py --run`, against this file as committed in `23493df`
(sha256 prefix `706bd52a80b60f63`, printed by the run). Nothing above this section was changed after the run.
Full output: `study/out/report_price_calendar.txt`.

**Price-matched gap** — how far the group moved against players who started the year at the same price:

| Group | Aug | Nov | Jan | Apr | Calendar? |
|---|---|---|---|---|---|
| **Rookie** | +1.9% | **+19.9%** | **+27.6%** | **+32.7%** | **Yes — rises from October on** |
| Second-Year | +1.2% | +5.3% | +6.3% | +11.8% | Not shown |
| **RB 26+** | −2.6% | −9.1% *(range just crosses zero)* | **−15.1%** | **−21.9%** | **Yes — falls from October on** |
| **WR 29+** | −3.5% | −3.5% | **−20.2%** | −24.3% *(3 of 4 years)* | **Yes — falls in December** |
| QB 32+ | −0.9% | −15.9% | −15.0% | −24.2% | Not shown — 17 players, too few |

Bold = SHOWN (≥5%, 99% range excludes zero, same direction in 4 of 5 years or 4 of 4).

**Predictions (§7):** two of six right. Rookies were **not** dearer in August, and were **far dearer, not cheaper,
by April**. Second-Year showed nothing. RB 26+ fell as predicted. WR 29+ was predicted "not shown" and fell clearly.
QB 32+ was not shown, as predicted, though its averages point the same way as the aging RBs and WRs.

**What it says, plainly:**

- **Nothing moves in the summer.** From May to August every group stays within 3.5% of veterans priced the same.
  The calendar is set by the **season**, not the offseason — rookies start pulling away in September (+7.0%).
- **Aging veterans don't fade — they drop.** The month-by-month calendar (reported only) shows the step: RB 26+
  −2.7% in September to −11.0% in October; QB 32+ −2.6% to −17.5% in the same month; WR 29+ −3.5% in November to
  −16.8% in December. **The window to move an aging veteran closes about a month into the season** (RBs and QBs) or
  just before the playoffs (WRs).
- **Rookies climb against veterans all season**, every year: November +2% to +30%, January +13% to +39%. The
  weakest year was the 2024 class (Nov +1.7%, Apr +3.9%).
- **In raw price (not price-matched, reported only)** rookies peak in **January–February** (+23% on May) and give
  back about 10 points by mid-April. Price-matched they keep rising because everyone else falls further in spring.

**Limits, restated:** rankings (FantasyPros consensus turned into values), not trade prices — the rookie rise may
partly be how rankers fold rookies in over a season, which this study cannot separate. Five years. Small
QB 32+ and WR 29+ groups. Gaps are measured on `L`, which reads small moves on cheap players a little low.

**What it leads to:** the newsletter article (§8). No engine change.
