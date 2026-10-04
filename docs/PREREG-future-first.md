# PRE-REGISTRATION — What Is A Future First Worth? One Early First vs Two Late Firsts

**Written:** 4 October 2026. No NFL production for these picks has been computed: the only runs were `--count` (slots,
names and name matches — no game data is read) and crash tests on synthetic outcomes (they prove the code runs and
the test can see what it is meant to see — nothing more). **These are famous players, though: general football
knowledge already says roughly how many of them turned out** (Justin Jefferson at 1.08, Trey Sermon at 1.09). The
prediction in §7 is made with that in mind, and is not blind.
**Status:** locks on commit. Changes after the first run go in Amendments, with a reason.
**Script:** `scripts/future-first-study.py` — `--count`, `--crash`, then `--run`, which refuses unless this file is
committed and unedited.
**What kind of study:** content for the newsletter. **It changes nothing in the engine** and needs no ship gate.

---

## 1. The Question

The most common pick trade in dynasty: **is one early first-round rookie pick worth two late firsts?** Asked here as:
in their first three seasons, do the players taken at 1.01–1.04 produce more **starter-level seasons** than twice what
the players taken at 1.09–1.12 produce?

---

## 2. The Rookie Drafts

- **Source:** Fantasy Football Calculator's Dynasty Rookie ADP, 12-team, fetched once by
  `scripts/fetch-ffc-rookie-adp.js` into `data/fixtures/ffc-rookie-adp-YYYY.json` (4 Oct 2026), response stored exactly
  as returned. FFC's API is free for personal and commercial use with attribution. ⚠ **Mock drafts** on FFC's site,
  human picks only — real people choosing rookies in order, but not real leagues. **1QB** format. **Late summer**: most
  years' window is the last two weeks of August.
- **Classes 2014–2023** — ten classes, so every pick has three seasons of outcomes (the 2023 class: 2023–2025). 2024
  failed to fetch and is not needed.
- **How many rookie drafts:** FFC's `total_drafts` counts every mock on the site; the real rookie-draft count is closer
  to the most-picked rookie's count — about **30 to 300 a year** (2018 ~29, 2021 ~31, 2014 ~41). First-round picks
  were drafted a median 27 times (fewest 3).
- **Does it agree with the consensus?** Checked before lock against DynastyProcess's 1QB rankings at the end of August,
  2020–2023 (same format, same time): rank agreement over the top 24 **0.84 / 0.92 / 0.92 / 0.90**; same players in the
  first round **12 / 9 / 10 / 11 of 12**. Even 2021, from ~31 drafts, agrees at 0.92.

**Slots:** QB/RB/WR/TE rows only, sorted by ADP, ranked within each class after drops: slot 1 = 1.01 … 12 = 1.12,
13–24 = round 2, 25–36 = round 3. **351 slots** kept.

**Tiers:** Early 1st = 1.01–1.04 · Mid 1st = 1.05–1.08 · **Late 1st = 1.09–1.12** · 2nd · 3rd. **40 picks in each
first-round tier.**

---

## 3. Joining FFC To NFL Players — A Listed Exception To "Never By Name"

FFC carries no ID shared with anyone. So each FFC row must match **exactly one** player with the **same normalised
name, same position, drafted the same year** (nflverse draft picks; DynastyProcess's crosswalk for undrafted players).
Six written exceptions, no others:

| FFC Name | Matched To | Why |
|---|---|---|
| Hollywood Brown (2019) | Marquise Brown | Nickname |
| Kenny Gainwell (2021) | Kenneth Gainwell | Nickname |
| Leontee Caroo (2016) | Leonte Carroo | FFC misspelling |
| Joseph Williams (2017) | Joe Williams | Name form |
| Joshua Palmer (2021) | Josh Palmer | Name form |
| Dri Archer (2014), listed RB | nflverse's WR record | Position label differs |

**Dropped before ranking (7):** **David Johnson, Tyler Lockett, Stefon Diggs** — 2015 draftees in FFC's **2016** rookie
list (that year's mocks let people take second-year players; see §5); a row named "Deleted Deleted" (2018); three
defensive or line players (2022).

---

## 4. The Outcome And The Test

- **Starter-level season:** season **total** points (DELTA scoring, `bt_pts`) inside the **top 12 at QB/TE, top 24 at
  RB/WR** that season, by nflverse position. **Total, not per game: missed time counts** (DELTA's settled rule). Nothing
  labels anyone injury-prone.
- **Each pick's outcome:** starter-level seasons in years 1–3 (0 to 3).
- **The test:** **D = Early 1st average − 2 × Late 1st average.**
  **D > 0:** one early first gave more than two late firsts. **D < 0:** two late firsts gave more.
- **SHOWN only if all three hold:**
  1. **Size:** |D| is at least 10% of the Early 1st average.
  2. **Not a fluke:** its **95%** range excludes zero — 4,000 resamples of the picks in each tier, seed 20261006. One
     test, so 95%.
  3. **Holds in both halves:** classes 2014–2018 and 2019–2023 point the same way.

**Reported only:** **elite seasons** (top 6 QB/TE, top 12 RB/WR) — stars win titles, and one star is not two
starters; the test without the 2016 class; every tier and every first-round slot (average starter seasons, share with
at least one); **what a future first gives on average** (any slot 1–12) and by class and position; the same test on
**DynastyProcess's superflex order** (May rankings, 2020–2023 — four classes, so it cannot be graded; it is there for
superflex readers).

---

## 5. Honest Limits

- **What the test can see.** Crash tests (three runs each): slot doesn't matter → "two lates win" **3 of 3**; early
  exactly 2× late → not shown **3 of 3**; early 3.5× late → "one early wins" **3 of 3**; early 2.75× late → not shown
  3 of 3. **So it can confirm one early first beating two lates only if early picks produce roughly 3.5× or more what
  late ones do, and the reverse only if early picks are barely better. In between — roughly 1.5× to 3× — reads "not
  shown",** which would mean the trade is close enough to fair that 40 picks a side cannot tell.
- **Mock drafts, 1QB, late summer,** 30–300 drafts a year. The agreement check (§2) says the order is sound.
- **2016** included non-rookies in its pool; they are dropped and the rest re-ranked, so 2016's slots may sit a little
  early. The result without 2016 is reported.
- **Three seasons only.** A pick's value after year three — the second contract, the late bloomer — is not counted.
- **Starter seasons add up across two players; real lineups don't always** (one starter slot, two starters). The
  elite-season figure is reported for that reason.
- nflverse labels a player by his latest position, so a season is ranked under that label.

---

## 6. Prior Work — Full Disclosure

- **Draft capital → breakout odds (handoff §6):** by **NFL** draft capital and position — e.g. top-10 WR 71% ever
  startable, Round 2 WR 43%, Day 3 WR 7%; peaks in year 2–3. Related outcome, different slotting (NFL draft, not rookie
  drafts) and no one-vs-two comparison.
- **Median, not mean, for late rookies (§6):** 88 late-round WRs, 36% under 2 PPG, 6% startable.
- **Rookie Sell-High, Pedigree Gap, Price Calendar:** rookie *prices*, not production by rookie-draft slot.
- **Seen before locking:** FFC metadata, names and slots for every class; the name-match results; the agreement check
  with DynastyProcess (§2) — order only, no outcomes; the 2026 pick prices printed while checking DynastyProcess's
  file layout (not used here); crash-test output. **And general knowledge of how these players' careers went.**

---

## 7. Stated In Advance, So It Can Be Wrong

- **Not shown.** Early firsts give clearly more than late firsts, but I expect somewhere near 2× — inside the range
  the test cannot settle — with D between −0.5 and +0.5.
- **Elite seasons (reported):** I expect early firsts to look much better here than on starter seasons — stars come
  from the top.

---

## 8. What It Could Lead To

A newsletter article — working title **"What Is A Future First Worth?"** — with the slot-by-slot table as its spine.
**No engine change.**

---

## Pre-Lock Checks (4 October 2026)

| Check | Result |
|---|---|
| Classes and slots | 2014–2023, 351 slots (31–36 a class; FFC listed fewer than 36 rookies in 2015, 2020, 2021) |
| First round by position | RB 50 · WR 50 · QB 14 · TE 6 |
| Name matching | Every remaining row matches exactly one player; 6 written exceptions (§3); 7 drops, each explained |
| Agreement with DynastyProcess 1QB, late Aug 2020–23 | 0.84 / 0.92 / 0.92 / 0.90; first-round overlap 12 / 9 / 10 / 11 of 12 |
| Crash tests | §5 — every expected outcome, three runs each |
| `--run` refuses while this file is uncommitted | Refused |

---

## Amendments

*(none)*

---

## Result (4 October 2026) — Not Shown: One Early First Is Worth About Two Late Firsts

Run once, `python3 scripts/future-first-study.py --run`, against this file as committed in `1ecc3f3`
(sha256 prefix `2c51a49ed5bf08f0`, printed by the run). Nothing above this section was changed after the run.
Full output: `study/out/report_future_first.txt`.

| Test | Early 1st | Late 1st | D = Early − 2 × Late (95% Range) | Halves (2014–18 / 2019–23) | Verdict |
|---|---|---|---|---|---|
| **Starter-level seasons, years 1–3** | 1.60 | 0.75 | **+0.10** (−0.60 to +0.75) | −0.30 / +0.50 | **Not shown** |
| Elite seasons (reported) | 0.90 | 0.38 | +0.15 (−0.43 to +0.70) | +0.05 / +0.25 | Not shown |
| Without the 2016 class (reported) | 1.69 | 0.81 | +0.08 (−0.61 to +0.75) | −0.44 / +0.50 | Not shown |

**Predictions (§7):** "not shown, early near 2× late, D between −0.5 and +0.5" — **right** (2.1×, +0.10). "Early firsts
look much better on elite seasons" — **mostly wrong**: 2.4× against 2.1×, a little better, not much.

**What it says, plainly:**

- **One early first ≈ two late firsts.** An early first gave 1.60 starter-level seasons in years 1–3; two late firsts
  gave 1.50. Stars barely change it (elite seasons: 0.90 against 0.76). **The common trade is about fair.** The two
  halves disagree in sign (−0.30 / +0.50), which is what "about fair" looks like.
- **The 1.01 stands apart:** 2.3 starter seasons on average and **10 of 10** had at least one. 1.02: 1.7, 8 of 10.
  Then it flattens — 1.03 (1.1) and 1.04 (1.3) look like mid-firsts (1.05–1.08: 0.7 to 1.2).
- **The curve, by tier** (starter seasons · at least one · elite): Early 1st 1.60 · 75% · 0.90 — Mid 1st 1.00 · 57%
  · 0.42 — Late 1st 0.75 · 48% · 0.38 — 2nd round 0.53 · 32% · 0.24 — 3rd round 0.28 · 22% · 0.13.
- **A future first, any slot:** 1.12 starter seasons on average; **60%** gave at least one in three years. By class
  it ranged from 0.67 (2016) to 1.50 (2020).
- **By position (first-rounders):** RB 1.32 (n 50) · WR 1.08 (n 50) · QB 0.71 (n 14) · TE 0.67 (n 6). Backs pay off
  sooner; the three-year window undercounts receivers who peak later. QBs here are 1QB-format picks.
- **Superflex order (DynastyProcess, 2020–23, reported only):** Early 1.69, Late 1.19 (16 picks each) — too few to
  grade, as §4 said; one half has no classes, so its "halves" figure is blank.

**Limits, restated:** mock drafts, 1QB, late summer; three seasons only; starter seasons add up across two players
more easily than real lineups do. The test could only have confirmed a gap of roughly 3.5× or more (§5) — the answer
it found, about 2×, sits squarely in the range it reads as "about fair".

**What it leads to:** the newsletter article (§8). No engine change.
