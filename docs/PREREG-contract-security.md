# PRE-REGISTRATION — Own Value Scale: Contract Security

**Drafted:** 10 November 2026. **Status: LOCKED** by the commit that adds the §10 decision below. The method is
`study/ovs_contract_security.py` as of commit 82d4351, unchanged since the crash tests. The planted crash test fell
short (§10); Steve chose to run as planned, accepting the lower power.

- **9 Nov, Steve:** contracts buy opportunity, not performance, and "I don't want to arbitrarily set a percentage."
- **10 Nov, Steve:**
  - "Yep sounds good, let's draft it."
  - He then accepted the bar in §3 and two changes to the draft (rookie deals out of the decision, sizes pulled toward
    zero): "I like your changes. Please update and let's do it."

---

## Plain-English Summary (For Steve)

**The question.** Does a player with years left on a deal his team signed keep his job, and score more than his
comparables say he should? Does a player in a contract year keep it less? Does the size of the deal matter?

**The data.** The contract history (`study/data/contract-history.json`, from original reports), the draft rule for
rookie deals, and nflverse rosters, stats and schedules. No OverTheCap or Spotrac.

**The method.** Each fantasy-relevant veteran from 2013–2022 gets the contract status he had at the next season's
kickoff. For each group, two things are compared with what his comparables predicted:

1. **Opportunity kept:** QB starts, or carries and targets, over the next three seasons.
2. **Points delivered:** fantasy points over the next three seasons, which is what dynasty value is.

**What you get.** A size with a margin of error, for example "2+ years left: 6% above his comparables, give or take 7".
It is not a pass/fail on the 2% rule: `POWER-contract-bump.md` showed no layer this small can ever pass that rule.

**The bar (§3).** A layer is used only if all of these hold:

- its 95% range excludes zero;
- opportunity moved the same way;
- it does no harm.

If used, the size is first pulled toward zero by how unsure it is.

## 1. The Rows And The Groups

**Rows.** Every veteran season 2013–2022 in which the player was fantasy-relevant (top QB 36, RB 60, WR 84, TE 36 by
fantasy points), measured entering the next season. All three following seasons are complete (through 2025): 2,162
rows.

**Base value.** The adopted preseason value, using `ovs_second_contract.base_value`'s matches and weights:

- era-adjusted comparables, three seasons ahead;
- offseason features;
- games out of matching.

Nothing else changes.

**Contract status at kickoff of season n** (n = the season after the row):

- **Which deal counts.** The latest one signed before that season's first regular-season game (nflverse schedules),
  skipping any deal released before that date.
- **Years left** = that deal's end − n:
  - 0 means **contract year**;
  - 1 means **1 year left**;
  - 2 or more means **2+ years left**.

**Who decides (Steve, 10 Nov).** Only deals a team chose to sign decide the result: veteran deals, extensions, tags, RFA
tenders, practice-squad deals and exercised fifth-year options.

- **Why rookie deals are out:** on a rookie deal, "years left" just means "how long he's been in the league". His
  comparables are already matched on that, and no team chose to commit.
- **Where they go:** rookie deals (the draft rule, and undrafted first deals) are reported separately.

**No deal at kickoff:**

- **Unsigned:** he wasn't on a club for its first game, or his next deal was signed after kickoff. Reported only.
- **Gap:** he was on a club with no deal recorded. Each one was looked up or excluded before lock, with no outcomes read:
  - **Added from original reports:** five deals. These are Cordarrelle Patterson (Oakland 2017–18), Seth Roberts
    (Baltimore 2019), Christine Michael (Indianapolis 2017), Mike Gillislee (New Orleans 2018) and Melvin Gordon
    (Baltimore 2023).
  - **Corrected:** two release dates. Ricky Seals-Jones 2019 was a waiver claim, so his deal carried on. Tajae
    Sharpe's 2020 release was in December, not September.
  - **Excluded:** the 14 that remain, listed in `study/out/contract_security_gaps.csv`. Most are 2015–16 retirements
    that the single-status roster files of those years can't separate.

**Final counts** (contracts and rosters only, no outcomes):

| Deals Teams Signed | Contract Year | 1 Year Left | 2+ Years Left | All |
|---|---|---|---|---|
| QB | 63 | 67 | 131 | 261 |
| RB | 125 | 84 | 96 | 305 |
| WR | 168 | 122 | 246 | 536 |
| TE | 62 | 60 | 115 | 237 |
| **All (decides)** | **418** | **333** | **588** | **1,339** |

Also: rookie deals 726 (reported), unsigned 83 (reported), gaps 14 (excluded).

## 2. The Measurements

**Points delivered, per group:**

- **The ratio:** total three-season points ÷ total base value, divided by the same ratio over all 1,339 deciding rows. A
  group at 1.06 delivered 6% more than its comparables predicted, relative to everyone.
- **The contract bump:** half the gap between 2+ years left and contract year.

**Opportunity kept, per group:**

- **What counts**, summed over the next three seasons (years out of the league count as zero):
  - QB: games he was named his team's starting QB (nflverse schedules);
  - RB: carries + targets;
  - WR/TE: targets.
- **What's predicted:** the same comparables' own opportunity, with the same weights.
- **The ratio:** actual ÷ predicted, worked out per position (the units differ), then combined by row counts. It's
  relative to all deciding rows, as above.

**Money committed:**

- **The measure:** the deal's average per year ÷ the salary cap of its first season (league announcements). Only
  sourced figures count, which covers 996 of the 1,339 rows.
- **The split:** thirds within each position, set from the contract data alone.
- **The money bump:** within each years-left group, (top-third ratio − bottom-third ratio) ÷ 2, relative to that group.
  The three groups are then combined by row counts.

**Ranges:** the 90% and 95% ranges, from resampling players 2,000 times, with all of a player's rows kept together.

**Correcting the lean:**

- **The problem:** the crash tests (§7) showed that with no real link, this kind of ratio reads slightly above zero,
  about +1.5 points (+1.3 and +1.7 in two runs).
- **The fix:**
  1. Shuffle the contract labels among players of the same position and season 200 times, and average what each
     estimate reads.
  2. Subtract that from the estimate and from both ends of its ranges.

  Shuffling removes any real effect, so this reveals nothing about it.

## 3. The Decision

**The contract-status layer is used if all three hold:**

1. **The range:** the corrected 95% range for the contract bump excludes zero.
2. **The opportunity check:** opportunity kept moves the same way, meaning its corrected bump has the same sign.
3. **No harm:**
   - Each season's rows take ratios learned from the other seasons, leaving out the two either side, which share
     outcome years. These are raw, uncorrected and unshrunk, which is the stricter test.
   - The typical miss on the deciding rows must be no more than 0.5% worse than the base.

**If used, each group's size is pulled toward zero:** size × max(0, 1 − (uncertainty ÷ size)²).

- The size is the corrected group ratio − 1, and the uncertainty is its spread across the resamples.
- A solid result keeps most of its size; a shaky one is cut back.
- The layer is labelled "Contract Security" and shown with its range.

**The money layer** is judged on conditions 1 and 2 for the money bump, on its own. It only applies on top of a status
layer that is used. If it's used:

- the top third is × (1 + pulled-in money bump);
- the bottom third is × (1 − pulled-in money bump).

**Otherwise:** no layer. The size is recorded as measured and not shown.

**The exception:** this is the stated exception to the 2% rule, per `POWER-contract-bump.md`. Steve agreed to it on 10
Nov.

## 4. Data Rules

**Rookie deals.** For players drafted 2011 or later, the deal ends at draft year + 3, unless an exercised option (+1)
or an extension replaces it. Earlier drafts and undrafted players use their recorded deals.

**Options** count only once exercised. Calvin Ridley's is 2022, as it stood on decision day.

**Extensions.**

- An extension's first season is the first new season.
- One signed before kickoff sets years left from its own end, because that security was known at the time.

**One-year deals** count as contract year: signed tags, RFA tenders and practice-squad deals. An unsigned tag is not a
deal (Le'Veon Bell 2018).

**Paused deals** use the end years as written: Ridley, Josh Gordon 2016–17, Bolden and Damien Williams (2020 opt-outs)
and Gronkowski (2019).

**Releases.** A waiver claim does not end a deal. A release before kickoff does.

**A deal with no signing date** counts from 1 March of its first season (10 deals).

**Unsourced rows.** 52 deciding rows use a low-confidence deal with no source. Their end years count; their money never
does. Results with them dropped are reported.

**Guaranteed money** is not used:

- it can include older years, so it can't be divided by Total;
- option guarantees changed with the 2018 class.

**`total` and `aav`** cover the new years only, except where `money_covers` says otherwise.

## 5. Reported, Deciding Nothing

- Each group's ratio by position.
- Rookie deals measured the same way.
- The unsigned group's points and opportunity against its comparables.
- Results without the unsourced rows.

## 6. Prior Looks

- **No outcome has been computed by contract group,** for opportunity or for points.
  - The counts come from contracts and rosters only.
  - The crash tests use shuffled labels.
  - The code check ran with every outcome shuffled (`--dry`).
- **The data checks used rosters only:** who changed teams, and who was on a club in week 1. No points or usage were
  read.
- **The second-contract study's crash test** (`PREREG-ovs-second-contract.md` §8) showed that the end-of-rookie-deal
  scaling is small. Some of those rows are among this study's deciding rows, so that size is partly known.
- **The power check** used made-up contracts.

## 7. Crash Tests, Before Lock

Both worlds use the real outcomes with the contract labels shuffled among players of the same position and season.
That removes any real effect without revealing it. The lean is corrected in every run, as in §2.

| World | What's Done | Bar |
|---|---|---|
| Noise | Shuffled labels, nothing planted | Range excludes zero in at most 15 of 200 |
| Planted 10% | Shuffled labels, then points × 0.9 in contract year and × 1.1 with 2+ left | Excludes zero in ≥ 160 of 200; average estimate within 2 points of 10% |
| Planted 5% | The same at 5% | Reported only |

- Condition 1 only. Opportunity is not planted.
- If the planted world fails, it goes to Steve before any real run.

## 8. Limits

- **It can't separate cause.** A team that pays a player may simply rate him. The layer captures both, which is fine
  for value, but it does not prove the contract itself kept him on the field.
- **It's small.** There are 1,339 deciding rows from 2013–2022. A real effect of about 5% will usually read "measured,
  not shown" (§7).
- **By position is too thin to decide,** so it's reported only.
- **QB starts use the schedule's named starter,** not DELTA's Start Profile rule, so the comparables' seasons back to
  2001 can be counted the same way.

## 9. Not Licensed Here

- **The live DELTA Score:** it already has a hand-set Contract axis (about 10%). Whether this result should reset that
  axis is a separate decision.
- **The site:** model values, buy/sell calls and the site itself don't change.
- **Position-specific layers.**

## 10. Amendments

**Crash tests (10 Nov, `study/out/ovs_contract_security_crash.json`): FAIL on the planted world.**

| World | Corrected (The Method) | Bar | Without The Correction |
|---|---|---|---|
| Noise | **10 of 200** excluded zero, average +0.1 | At most 15 | 15 of 200, average +1.7 |
| Planted 10% | **127 of 200 (64%)**, average 9.0 | 160 of 200, within 2 points | 172 of 200, average 11.2 |
| Planted 5% | 50 of 200, average 4.6 | Reported only | 87 of 200, average 6.5 |

**What it means:**

- **The correction works.** With nothing planted, the range wrongly excludes zero 5% of the time, as it should, and
  the average sits at zero.
  - Without the correction, the method reads about 1.7 points high and is wrong 7.5% of the time.
  - So the uncorrected 172 of 200 overstates the test's power.
- **The test is too small to reliably catch a real 10% bump.** With 1,339 rows the 95% range is about ±9 points wide.
  A true 10% bump clears it about 2 times in 3, and a true 5% bump about 1 time in 4.
- **No real run has been made, and no outcome by contract group has been read.** Per §7, this goes to Steve.

**The options, measured the same way** (100 runs each, shuffled labels; `study/ovs_contract_security_options.py`,
`study/out/ovs_contract_security_power_options.json`):

| Option | Rows | Catches A Real 10% | Catches A Real 5% | Fake Layer Shown (Nothing Real) |
|---|---|---|---|---|
| As drafted: team-signed deals, 95% range | 1,339 | 69 of 100 | 23 of 100 | 2 of 100 |
| Team-signed deals, 90% range | 1,339 | 80 of 100 | 29 of 100 | 9 of 100 |
| Rookie deals back in, 95% range | 2,065 | 84 of 100 | 34 of 100 | 3 of 100 |
| Rookie deals back in, 90% range | 2,065 | 89 of 100 | 52 of 100 | 6 of 100 |

**The rookie rows assume too much.** Those runs plant the bump on rookie deals too, so they assume rookie deals react
the same way. If they don't react, mixing them in waters a real bump down by about a third. Their power is the
best case.

**Steve's decision (10 Nov, before any real run):** "I guess lets run it as planned."

- **Nothing changes:** the method, the bar (corrected 95% range), and team-signed deals only.
- **The lower power is accepted:** a real 10% bump is shown about 2 times in 3.
- **How to read a "not shown" result:** it means the size couldn't be pinned down, not that contracts don't matter.

**Wording correction (10 Nov, after the run; the method is unchanged):**

- "Points delivered" is the studies' usual outcome, FV: value over the replacement line (QB 24, RB 30, WR 42, TE 14)
  summed over the next three seasons. It is not raw fantasy points.
- A season below the line counts as zero. That's why all 83 unsigned rows read zero.
- The code was always this; only the plain-English description in §2 was loose.

## 11. Result (The One Real Run, 10 Nov, `study/out/ovs_contract_security_results.json`)

**The contract-status layer passes all three conditions and is used.**

| Contract Status At Kickoff | Rows | Value Delivered vs Comparables (95% Range) | Opportunity Kept vs Comparables (95% Range) | Layer (Pulled Toward Zero) |
|---|---|---|---|---|
| Contract year | 418 | 0.75 (0.60–0.90) | 0.90 (0.84–0.96) | **× 0.77** |
| 1 year left | 333 | 0.91 (0.80–1.02) | 0.96 (0.92–1.01) | **× 0.95** |
| 2+ years left | 588 | 1.09 (1.03–1.15) | 1.06 (1.03–1.09) | **× 1.08** |

1. **The contract bump: +17.1%** (95% range +7.4% to +26.3%, after removing a +1.6 lean). The range excludes zero.
2. **Opportunity moved the same way: +7.9%** (+3.9% to +12.0%).
3. **No harm:** 0.28% worse on the deciding rows, inside the 0.5% allowance.
   - **It does not make the values more accurate.** The power check said a layer this size wouldn't. It passes the
     guard only.

**Money committed: not used.**

- Value: +8.5% (−11.3% to +24.0%).
- Opportunity: −1.3% (−8.6% to +6.1%).
- Once years left is known, how much the deal pays adds nothing that can be measured.

**Reported, deciding nothing:**

- **By position, contract bump:**
  - **WR +25%** (+15% to +36%), the only position whose range excludes zero.
  - QB +9% (−15% to +29%).
  - RB +14% (−8% to +36%).
  - TE +33% (−1% to +53%).
- **Without the 52 unsourced rows:** +18.3% (+7.9% to +27.7%), essentially the same.
- **Rookie deals, measured the same way:** +12.2% (0.0% to +23.2%), 726 rows.
  - The effect shows here too, so §1's reason for leaving them out ("years left is just experience") looks only partly
    right.
  - They stay out of the decision as locked.
- **Unsigned at kickoff (83 rows):** zero value delivered against comparables who predicted some. Opportunity was 45%
  of what the comparables had.

**What it means:**

- **The direction is the one Steve predicted.** Players with years left on a deal their team signed keep more of their
  opportunity and deliver more value than their comparables. Players in a contract year keep less and deliver much less.
- **It still can't separate cause (§8).** A short deal is partly the team saying it doesn't trust the player. The layer
  captures that signal as well as the security itself.
- **Licensed:** a labelled Contract Security layer in the Own Value Scale (§3).
- **Not licensed (§9):** the site, the DELTA Score, or a per-position layer.
