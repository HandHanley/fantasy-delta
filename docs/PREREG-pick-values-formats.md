# PRE-REGISTRATION — Rookie Pick Values By League Format

**Drafted:** 7 November 2026. **Status: LOCKED 7 Nov 2026 (after amendment A1, §9).** Locked by committing this document with
`study/pick_values_formats.py` before the confirmatory run. Changes after that are amendments (§9).

Follows `docs/PREREG-pick-values.md` (locked `d5a2a2d`, run 7 Nov: R = 1.39 in DELTA's format). Same method, same
data, same decision rule; what changes is the league format.

---

## Plain-English Summary (For Steve)

A pick's value depends on the league. In a 14-team league the 3rd round reaches deeper into the class; in full PPR
receivers count for more; in superflex quarterbacks count for far more. So we rebuild everything — the five-season
values, the player ruler, the pick values and the fairness check — once for each format, and price picks by **pick
number** (the 10th rookie taken), so a "1.10" means the same thing in a 10-team league as a "1.10" does in a 12-team one.

What it can't fix: the draft order still comes from 12-team **1QB** mock drafts for every format. For superflex leagues
that's the known gap (no long enough superflex rookie history exists for free; see §7).

## 1. Formats (36)

| Setting | Options |
|---|---|
| League size | 10, 12, 14 teams |
| Quarterbacks | 1QB, Superflex |
| Scoring | Standard, Half PPR, Full PPR |
| Tight end premium | Off, On (+0.5 per TE catch) |

**Points:** standard fantasy points + (0, 0.5 or 1) × receptions + (0 or 0.5) × TE receptions. DELTA's own format
(12-team, superflex, half PPR, TE premium) reproduces today's numbers exactly (asserted).

**Replacement lines** (the Nth-best player at the position each season), scaled from DELTA's lineup (one QB, two RB,
three WR, one TE, two flex, plus the superflex slot): per team, QB 2 in superflex and 1 in 1QB; RB 2.5; WR 3.5;
TE 14 ÷ 12. Rounded to whole players:

| Teams | QB (Superflex / 1QB) | RB | WR | TE |
|---|---|---|---|---|
| 10 | 20 / 10 | 25 | 35 | 12 |
| 12 | 24 / 12 | 30 | 42 | 14 |
| 14 | 28 / 14 | 35 | 49 | 16 |

## 2. Method, Per Format

Everything as in `PREREG-pick-values.md` §3–§5, rebuilt from scratch for the format: outcomes (FV5) and the
production features used for matching, veterans' Own Value Scale values, tier values (leave one class out), matched
veterans (±10%, then ±20%, 10 minimum), R and its 95% range from 4,000 resamples (seed 20261107).

**Decision, per format (amendment A1):** that format's picks × that format's measured R, always. The 95% range is
reported beside it as how sure we are; it no longer decides whether the fix applies. The 1.01 is priced as part of slots 1–4 (Steve's decision, 7 Nov).

## 3. Pricing By Pick Number

Picks are priced by overall rookie taken (slot), in the same five bins the study measured: slots 1–4, 5–8, 9–12,
13–24, 25–36. A league's pick maps to a slot: pick `r.p` in an `n`-team league is slot `(r − 1) × n + p`. Example:
in a 10-team league, 1.09, 1.10, 2.01 and 2.02 are slots 9–12. **Slots past 36** (late 3rd round in a 14-team league)
have no measured value; by convention they take the slots 25–36 value, which is likely generous, stated as such.
Conventions carry over: a pick a year further out × 0.9; a 1st with its slot unknown = average of the first round's
slots for that league size.

## 4. Crash Tests, Before Lock

The locked test (`test_pick_values.py`) passed in DELTA's format. Rerun on the two formats furthest from it — **10-team
1QB Standard, no TE premium** and **14-team Superflex Full PPR with TE premium** — at 100 runs each, 1,000 resamples,
same worlds and bars: fair world range includes 1.0 in ≥ 90%; R_true = 0.7 excluded in ≥ 80%. Either failing is
reported before any real result.

## 5. Reported, Deciding Nothing

Per format: each slot bin on that format's ruler (its 10,000 = that format's top 2025 Own Value Scale value), R for QB
picks and for the rest, and the value of a pick a year out.

**One prediction, stated now (exploratory):** if the quarterback part of today's 1.39 comes from 1QB draft order meeting
superflex scoring, then the QB picks' R should be much closer to 1 in 1QB formats than in superflex ones.

## 6. What Each Result Allows (Steve's OK Needed)

A table of pick values by format and pick number for the Trade Calc. Nothing on the site changes from this study.

## 7. Limits, Stated Now

- **1QB draft order for every format.** Free superflex rookie history: DynastyProcess superflex rankings start in 2019
  (three classes with five seasons done). DLF has 2QB rookie mock drafts back to the 2015 class but is paid and
  copyrighted; using it would need their permission.
- **Same 279 picks and eight classes**, so every format shares the same small-sample uncertainty.
- **36 formats, 36 checks.** A few could cross the line by chance; each format's own range is what decides it.
- **Lineups are scaled, not surveyed.** Leagues with more flex spots or 2 TE starts would move the lines.

## 8. Not Licensed Here

Superflex rookie-draft order, class strength, landing spot, and anything after the NFL draft.

## 9. Amendments

**Before lock**
- **Smoke test (7 Nov).** DELTA's own format through the new code: R 1.392, range 1.12–1.78, slot values 7,368 /
  5,088 / 4,105 / 2,653 / 1,595 — identical to the locked run (asserted). No other format has been run.
- **Crash tests (7 Nov, `study/out/pick_values_formats_crash.json`, 100 runs, 1,000 resamples):**

| Format | Fair World: Range Included 1.0 (Bar 90) | 30% Tilt: Caught (Bar 80) | Result |
|---|---|---|---|
| 10-team 1QB Standard | 100 of 100 | **45 of 100** | **Fail** |
| 14-team Superflex Full PPR TE Premium | 100 of 100 | 96 of 100 | Pass |

  **FAIL.** In the shallow format the study can't reliably see a 30% tilt: fewer players clear the replacement lines
  there, so more picks and veterans score zero and the ratio gets noisy. Never a false alarm in either. Per §4, this
  goes to Steve before any real result; the confirmatory run is on hold.
- **A1 (7 Nov), Steve's choice after the failed crash test.** Apply each format's measured R always (§2), instead of
  only when its range excludes 1.0. Reason: the crash tests show the measured R lands in the right place on average in
  both formats (no tilt: typical 1.01; planted 0.70: typical 0.71–0.73); in shallow formats it is only noisier. Under the
  old rule a shallow format would usually get no fix even when picks are underpriced, and in DELTA's format the fix was
  ×1.39. Formats with wide ranges are flagged, and the study is rerun as more classes finish five seasons. In DELTA's
  format both rules give the same answer (its range excluded 1.0), asserted. Decided before any real result outside
  DELTA's own format was seen.

## 10. Results (7 Nov 2026, Run Once)

`study/out/pick_values_formats_results.json`. All 279 picks scored in every format. DELTA's format reproduced the
locked run exactly (asserted).

**Picks are underpriced in every one of the 36 formats, by a similar amount: R from 1.27 to 1.52.** Every format's range
excluded 1.0 (widths 0.54–0.86), so under the old rule the fix would have applied everywhere too; amendment A1 changed
no answer. Values are on each format's own ruler (its 10,000 = its top 2025 player).

| Format | Fix (R) | 95% Range | Slots 1–4 | 5–8 | 9–12 | 13–24 | 25–36 | 1st, Slot Unknown |
|---|---|---|---|---|---|---|---|---|
| 10-team 1QB Standard | ×1.40 | 1.12–1.86 | 8,258 | 5,212 | 3,748 | 2,216 | 1,072 | 6,138 |
| 10-team 1QB Standard TE Premium | ×1.49 | 1.13–1.88 | 8,809 | 5,549 | 4,079 | 2,361 | 1,148 | 6,559 |
| 10-team 1QB Half PPR | ×1.43 | 1.14–1.97 | 7,654 | 4,832 | 3,469 | 2,047 | 1,011 | 5,688 |
| 10-team 1QB Half PPR TE Premium | ×1.40 | 1.17–2.01 | 7,531 | 4,744 | 3,470 | 2,016 | 1,004 | 5,604 |
| 10-team 1QB Full PPR | ×1.52 | 1.21–2.07 | 7,799 | 5,044 | 3,526 | 2,094 | 1,073 | 5,842 |
| 10-team 1QB Full PPR TE Premium | ×1.49 | 1.22–2.06 | 7,665 | 4,942 | 3,515 | 2,065 | 1,066 | 5,746 |
| 10-team Superflex Standard | ×1.41 | 1.11–1.80 | 7,497 | 5,004 | 3,888 | 2,525 | 1,412 | 5,778 |
| 10-team Superflex Standard TE Premium | ×1.36 | 1.09–1.82 | 7,240 | 4,823 | 3,816 | 2,434 | 1,366 | 5,588 |
| 10-team Superflex Half PPR | ×1.44 | 1.12–1.92 | 8,066 | 5,357 | 4,126 | 2,653 | 1,489 | 6,194 |
| 10-team Superflex Half PPR TE Premium | ×1.43 | 1.15–1.97 | 8,010 | 5,308 | 4,153 | 2,636 | 1,487 | 6,158 |
| 10-team Superflex Full PPR | ×1.39 | 1.16–1.95 | 7,392 | 4,997 | 3,731 | 2,395 | 1,365 | 5,702 |
| 10-team Superflex Full PPR TE Premium | ×1.42 | 1.17–1.96 | 7,581 | 5,110 | 3,873 | 2,462 | 1,410 | 5,851 |
| 12-team 1QB Standard | ×1.36 | 1.11–1.76 | 8,432 | 5,328 | 3,841 | 2,388 | 1,230 | 5,867 |
| 12-team 1QB Standard TE Premium | ×1.35 | 1.13–1.78 | 8,403 | 5,298 | 3,853 | 2,380 | 1,242 | 5,851 |
| 12-team 1QB Half PPR | ×1.34 | 1.13–1.77 | 7,602 | 4,909 | 3,467 | 2,172 | 1,171 | 5,326 |
| 12-team 1QB Half PPR TE Premium | ×1.30 | 1.14–1.79 | 7,393 | 4,763 | 3,432 | 2,128 | 1,159 | 5,196 |
| 12-team 1QB Full PPR | ×1.43 | 1.17–1.82 | 7,699 | 5,156 | 3,590 | 2,247 | 1,257 | 5,482 |
| 12-team 1QB Full PPR TE Premium | ×1.47 | 1.16–1.84 | 7,935 | 5,297 | 3,747 | 2,325 | 1,312 | 5,660 |
| 12-team Superflex Standard | ×1.39 | 1.12–1.75 | 6,610 | 4,520 | 3,697 | 2,403 | 1,407 | 4,942 |
| 12-team Superflex Standard TE Premium | ×1.39 | 1.12–1.73 | 6,618 | 4,516 | 3,718 | 2,406 | 1,419 | 4,951 |
| 12-team Superflex Half PPR | ×1.33 | 1.12–1.75 | 7,047 | 4,878 | 3,872 | 2,524 | 1,508 | 5,266 |
| 12-team Superflex Half PPR TE Premium | ×1.39 | 1.12–1.78 | 7,368 | 5,088 | 4,105 | 2,653 | 1,595 | 5,520 |
| 12-team Superflex Full PPR | ×1.29 | 1.11–1.80 | 7,244 | 5,152 | 3,994 | 2,593 | 1,578 | 5,463 |
| 12-team Superflex Full PPR TE Premium | ×1.35 | 1.13–1.78 | 7,557 | 5,359 | 4,209 | 2,712 | 1,660 | 5,708 |
| 14-team 1QB Standard | ×1.43 | 1.13–1.73 | 9,012 | 5,750 | 4,130 | 2,634 | 1,435 | 5,774 |
| 14-team 1QB Standard TE Premium | ×1.44 | 1.15–1.73 | 9,116 | 5,790 | 4,247 | 2,682 | 1,475 | 5,855 |
| 14-team 1QB Half PPR | ×1.30 | 1.13–1.67 | 7,568 | 5,090 | 3,534 | 2,276 | 1,288 | 4,951 |
| 14-team 1QB Half PPR TE Premium | ×1.27 | 1.14–1.71 | 7,421 | 4,975 | 3,504 | 2,240 | 1,274 | 4,863 |
| 14-team 1QB Full PPR | ×1.36 | 1.15–1.72 | 7,679 | 5,334 | 3,633 | 2,368 | 1,372 | 5,094 |
| 14-team 1QB Full PPR TE Premium | ×1.38 | 1.15–1.73 | 7,802 | 5,410 | 3,749 | 2,431 | 1,411 | 5,193 |
| 14-team Superflex Standard | ×1.45 | 1.11–1.69 | 6,224 | 4,234 | 3,904 | 2,443 | 1,485 | 4,452 |
| 14-team Superflex Standard TE Premium | ×1.39 | 1.12–1.68 | 6,004 | 4,066 | 3,806 | 2,365 | 1,445 | 4,302 |
| 14-team Superflex Half PPR | ×1.39 | 1.11–1.66 | 6,554 | 4,649 | 4,069 | 2,569 | 1,587 | 4,730 |
| 14-team Superflex Half PPR TE Premium | ×1.37 | 1.12–1.68 | 6,497 | 4,595 | 4,063 | 2,550 | 1,581 | 4,694 |
| 14-team Superflex Full PPR | ×1.30 | 1.11–1.69 | 6,760 | 4,900 | 4,138 | 2,640 | 1,646 | 4,891 |
| 14-team Superflex Full PPR TE Premium | ×1.31 | 1.11–1.70 | 6,844 | 4,952 | 4,237 | 2,693 | 1,680 | 4,966 |

**The §5 prediction held.** QB picks' R: 0.97–1.52 in 1QB formats, 2.86–4.70 in superflex. In 1QB
leagues the 1QB draft order fits and QB picks are priced about right; in superflex the QBs are badly underpriced
because 1QB drafters take them too late. RB/WR/TE picks: 1.28–1.58 in 1QB formats, 1.07–1.26 in superflex.

**Reading the table.** Pick `r.p` in an `n`-team league is slot `(r − 1) × n + p` (§3): in a 10-team league 1.09–2.02
are slots 9–12. Slots past 36 take the 25–36 value (convention). A pick a year out is 0.9 of these. Early picks sit
lower on superflex rulers because a superflex ruler's 10,000 is a quarterback worth far more than any 1QB top player.

**What it allows (Steve's OK needed):** this table as the Trade Calc's pick values by format. The superflex rows carry
the 1QB-order caveat until a superflex order is built (next: a scarcity-based superflex order, its own plan).

**Final table (7 Nov).** The Trade Calc's pick values for all 36 formats are in `study/out/pick_values_final.json`:
1QB formats from this study, superflex formats from `docs/PREREG-superflex-pick-order.md` (which passed), with
Steve's rule that a later pick is never worth more than an earlier one (no 1QB format needed it).
