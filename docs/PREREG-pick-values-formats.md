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
