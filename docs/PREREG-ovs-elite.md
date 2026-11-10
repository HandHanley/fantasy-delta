# PRE-REGISTRATION — Own Value Scale: Do We Shortchange The Elite?

**Drafted:** 10 November 2026. **Status: NOT LOCKED. Both crash tests failed (§9), so no real run was made.** Steve: "I
think we should absolutely do that test," then "yep lets run it."

---

## Plain-English Summary (For Steve)

**Why.** The position-balance decision (keep DELTA's own exchange rate, or borrow the market's) turns mostly on TEs. Our
average TE values match what TEs went on to deliver. But that average could hide a miss at the very top. If DELTA
prices the typical TE right and shortchanges the Kelce types, the two would cancel out.

**Steve's point (10 Nov).** At TE, nearly all the value sits in two or three players. Here is the average season, full
PPR, 2013–2025, measured against the average starter (QB 24, RB 30, WR 42, TE 12 in a 12-team superflex):

| Position | #1 Above The Average Starter | #5 Above The Average Starter | #1 Worth This Many #5s |
|---|---|---|---|
| QB | 126 | 49 | 1.6 |
| RB | 164 | 62 | 1.8 |
| WR | 145 | 70 | 1.6 |
| TE | 85 | 6 | 2.3 |

The last column is measured above the starter line. The TE5 is barely better than an average starting TE, and the TE1
is far above everyone. The steeper the drop, the more it costs to pull an elite player back toward the pack. So if our
method does that, TE is where it would hurt most.

**The question.** Each season, the players DELTA rated top 3 at their position: did they go on to deliver more than
their values said, compared with the next tier (ranked 4–24)?

**What you get.** For each position, a number. For example, "DELTA's top-3 TEs delivered 1.25× what their values said,
relative to the next tier, give or take 0.3." If the range clears 1, the top 3 get a measured lift, pulled toward zero
by how unsure it is. That is the same framework as Contract Security.

## 1. The Rows And The Groups

**Rows.** The veteran preseason rows 2013–2022 (the usual 5,693 test rows), all with three complete seasons after.
Rookies are not in it, because they have no veteran value yet.

**Base value.** The adopted preseason value, the same as `ovs_contract_security.py`, from
`ovs_second_contract.base_value`.

**Groups.** Within each position and season, rank the rows by base value:

- **Elite:** ranks 1–3, 30 rows per position.
- **Next tier:** ranks 4–24, 210 rows per position.
- Everyone else is not used.

## 2. The Measurement

- **Outcome:** FV3, value over the starter line (QB 24, RB 30, WR 42, TE 14) over the next three seasons. Scoring is
  half PPR with TE premium, as all the value studies are scored.
- **Elite ratio, per position:** (outcome ÷ value, summed over the elite) ÷ (the same for the next tier). Above 1 means
  DELTA's top 3 delivered more than their values said, compared with the next tier.
- **Pooled:** the four positions' elite ratios, combined by row counts.
- **Ranges:** the 90% and 95% ranges, from resampling players 2,000 times.
- **Lean correction:** the same idea as Contract Security, built for this question.
  1. Within each position and season, shuffle the outcome-to-value ratios among ranks 1–24. That breaks any link
     between being elite and over- or under-delivering.
  2. Do that 200 times, and take the average reading as the lean.
  3. Subtract it from the estimate and from both ends of its ranges.

## 3. The Decision

**Q1, TEs (Steve's question).** If the corrected 95% range for the TE elite ratio excludes 1, the TE top 3 get × the
ratio, pulled toward zero: size × max(0, 1 − (uncertainty ÷ size)²).

**Q2, all positions pooled.** The same rule. It covers the case where our method shortchanges elite players everywhere.

- **If both pass,** TEs use their own number.
- **Both directions count.** If the range sits wholly below 1, the elite are overpriced, and they come down.

**No harm, for any layer used:**

- Each season's rows take ratios learned from the other seasons, leaving out the two either side.
- The typical miss on that position's ranks 1–24 must be no more than 0.5% worse than the base.

**This is a measured-size layer,** the same exception to the 2% rule as Contract Security.

## 4. Reported, Deciding Nothing

- **The QB, RB and WR elite ratios,** each with its range.
- **Elite as the top 1 and as the top 5,** instead of the top 3.
- **Staying power by position, from actual finishes:**
  - how often a top-3 finisher is top 3 again next season;
  - how often he's top 3 in at least two of the next three.
- **Which players make up the TE elite rows,** listed by name.

## 5. Prior Looks

- **No elite ratio has been computed,** for any position.
- **Today's season-points-by-rank tables and the list of TE1 finishers** (Kelce 7 of 13, Gronkowski 2, and so on) come
  from season stats only. No DELTA values were involved.
- **The 9 Nov TE calibration check:** DELTA's TE values matched what TEs delivered, at 99% on average. That's the
  average this study looks underneath.
- **The "true peers for elite players" test** (`PREREG-ovs-peers.md`) matched elite players only to elite peers. It came
  out 4.1% worse overall. It changed who the comparables are, and it did not measure an elite ratio.

## 6. Crash Tests, Before Lock

Both worlds use the null in §2: ratios shuffled within position and season among ranks 1–24.

| World | What's Done | Bar |
|---|---|---|
| Noise | Nothing planted | The TE range and the pooled range each exclude 1 in at most 15 of 200 |
| Planted 25% | Elite outcomes × 1.25 | TE excludes 1 in ≥ 160 of 200; pooled the same; average estimate within 5 points |
| Planted 15% | Elite outcomes × 1.15 | Reported only |

- **Why 25%:** the market prices Bowers and McBride well above where DELTA has them. A shortchange worth fixing would
  have to be large.
- **If the planted world fails,** it goes to Steve before any real run.

## 7. Limits

- **It's small:** 30 elite TE seasons.
- **It can't say why.** If elite TEs over-deliver, it may be thin comparables (few past players look like Bowers), or
  something else.
- **There's a cliff:** a lift on ranks 1–3 only puts a step between the 3rd and 4th player.
- **Only veterans:** rookie-year elites, such as Bowers in 2024, are not in it.
- **Scoring:** half PPR with TE premium, as all the value studies are scored.

## 8. Not Licensed Here

- **The position-balance decision:** it informs that decision but does not make it.
- **The site, the DELTA Score and buy/sell calls.**

## 9. Amendments

**Crash tests (10 Nov, `study/out/ovs_elite_crash.json`): FAIL for both questions. No real run was made.**

| World | TE: Range Excludes 1 | TE: Average Estimate | Pooled: Range Excludes 1 | Pooled: Average Estimate | Bar |
|---|---|---|---|---|---|
| Noise | 14 of 200 | 0.98 | 10 of 200 | 0.99 | At most 15 |
| Planted 25% | **10 of 200** | 1.26 | **85 of 200** | 1.26 | 160 of 200 |
| Planted 15% | 22 of 200 | 1.25 | 37 of 200 | 1.17 | Reported only |

**What it means:**

- **For TEs, the test is blind.** If DELTA really shortchanged its top-3 TEs by 25%, the test would notice 5% of the
  time, the same as with nothing planted.
- **Why it's blind:** there are only 30 elite TE seasons, and a TE's next three seasons swing so widely that 30 of them
  can't pin down even a large gap.
- **Pooled across positions** catches a 25% gap 4 times in 10, still well short of the bar.

**A second design was tried,** with its power measured the same way (`study/ovs_elite_options.py`,
`study/out/ovs_elite_power_options.json`). It is a "stretch" test: does delivered value rise faster than DELTA's value
across a whole position, which would mean values are too bunched together? With the same 25% planted on the top 3:

| Stretch Test | TE | WR |
|---|---|---|
| Ranks 1–24 | 5 of 100 | 20 of 100 |
| Every veteran row | 3 of 100 | 1 of 100 |

It is no better. History from 2013–2022 cannot tell whether DELTA shortchanges elite TEs, even by a quarter.

**Prior look disclosed.** The code check (`--dry`) printed the §4 staying-power numbers. Those come from actual
finishes, with no DELTA values involved. How often a top-3 finisher (2013–2022) was top 3 again the next season:

- TE: 40%
- WR: 27%
- RB: 23%
- QB: 17%

How often he was top 3 in at least two of the next three seasons:

- TE: 27%
- WR: 17%
- QB: 13%
- RB: 7%

**Per §6, this goes to Steve.** Nothing on the site or in the values changed.
