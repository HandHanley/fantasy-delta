# PRE-REGISTRATION — Contract Security: A Contract Year At The End Of A Multi-Year Deal

**Drafted:** 25 November 2026, before any outcome has been read for this split. **Status: LOCKED** by committing this
document with `study/ovs_contract_length.py`. Crash test next; the real run only if it passes. Steve, 25 Nov: "Yeah go
ahead and write and deploy number 1 and let's see what it says."

---

## Plain-English Summary (For Steve)

**The question.** DELTA cuts a player's value by 23% when next season is the last year of his deal (the Contract
Security layer, `PREREG-contract-security.md`). The likely reason it works: a short deal is a team hedging its bet.
Lamar Jackson is in the last year of a five-year deal Baltimore chose; that isn't a hedge.

**The test.** Split the contract-year players into two groups and measure each one the same way the layer was measured:

- **One-year deal:** the deal in force covers one season. One-year veteran deals, franchise and transition tags, RFA
  tenders, exercised fifth-year options and practice-squad deals. 291 of the 418 contract-year rows.
- **Multi-year deal:** the deal covers two or more seasons and next season is its last. 127 rows.

If the multi-year group clearly keeps more of its value than the one-year group, the contract-year cut splits into two.
Otherwise nothing changes.

**Why two or more years, not four or more.** Counted from the contracts alone before anything else: only 31 contract-
year rows sit at the end of a deal of four or more years (most long deals get extended or cut before their last year),
too few to measure. Two or more gives 127.

## 1. Rows, Base Value, Outcome

Exactly as `PREREG-contract-security.md` §1–§2: fantasy-relevant veterans 2013–2022 on deals a team signed (1,339
rows), the adopted preseason value as the base, FV over the next three seasons as points delivered, QB starts / RB
carries + targets / WR and TE targets as opportunity, players resampled 2,000 times. The script checks that its
contract labels reproduce the adopted study's file exactly.

**Deal length** = the `years` the deal covers (`study/data/contract-history.json`), or end − first + 1 where `years`
is blank. Counts (contracts only):

| Contract-Year Rows | QB | RB | WR | TE | All |
|---|---|---|---|---|---|
| One-year deal | 40 | 91 | 121 | 39 | 291 |
| Multi-year deal | 23 | 34 | 47 | 23 | 127 |

## 2. The Measurement

- **Each group's ratio:** its total points ÷ total base value, divided by the same ratio over all 1,339 rows (as the
  adopted layer).
- **The gap:** multi-year ratio − one-year ratio, with its 95% range from the resampling.
- **Lean correction:** the one-year / multi-year labels shuffled among contract-year rows of the same position and
  season 200 times; the average gap read is subtracted from the estimate and both ends of its range.
- **Opportunity gap:** the same on opportunity kept, worked out per position and combined by row counts.

## 3. Decision

The contract-year group splits in two if all three hold:

1. The corrected 95% range of the points gap excludes zero.
2. The opportunity gap has the same sign.
3. **No harm:** leave-season-out ratios (each season and the two either side left out), four groups vs today's three:
   typical miss on the 1,339 rows no more than 0.5% worse.

**If it splits,** each contract-year group's factor is 1 + its ratio − 1 pulled toward zero by its uncertainty (as the
adopted layer). "1 year left" (×0.95) and "2+ years left" (×1.08) are unchanged. **If not,** the layer stays as it is.

This is a measured layer, the same stated exception to the 2% rule as the layer it refines (`POWER-contract-bump.md`).

## 4. Crash Test, Before Any Real Run

Labels shuffled within contract-year rows of the same position and season (removing any real link), then a gap
planted: one-year rows' outcomes × (1 − gap ÷ 2), multi-year rows × (1 + gap ÷ 2). 200 runs each:

- **No gap:** the corrected range may exclude zero at most 15 times.
- **Gap of 0.25** (a multi-year contract year keeping about a third more of its value than a one-year one): must be
  caught at least 160 times.
- **Gap of 0.15:** reported.

If it fails, back to Steve before any real run.

## 5. Reported, Deciding Nothing

The gap by position (where a position has 5+ multi-year rows); each group's ratio; what the 2026 build would change
if it splits (Lamar Jackson and others in the last year of a multi-year deal; C.J. Stroud's exercised option is a
one-year deal).

## 6. Prior Looks

The adopted layer's results (`PREREG-contract-security.md` §11): the contract-year group as a whole delivered 0.75 of
its base value; by position, the QB contract bump was +9% (−15% to +29%). **No outcome has been read with the one-year
/ multi-year split.**

## 7. Limits

- 127 multi-year rows: the range will be wide.
- Deal length is one signal of a team's commitment; money (the deal's share of the cap) was tested in the adopted study
  and added nothing measurable.
