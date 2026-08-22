# PRE-REGISTRATION — RB dominator weight

**Written:** 22 August 2026, before any confirmatory result exists.
**Status:** locked on commit. Changes after the first confirmatory run must be recorded
as amendments below, with a reason, not edited in silently.

---

## 1. What is already decided, and is NOT what this study tests

RB dDOM currently uses `rdom` alone — the player's share of team rushing yards and TDs.
It ignores receiving entirely. For a back who takes ~35% of his scrimmage yards through
the air (Jahmyr Gibbs), the headline number on his card describes roughly two thirds of
his game.

**The decision to include receiving is already made and is not on trial here.** A metric
called a dominator that omits a third of a player's production is measuring the wrong
construct. That argument does not depend on a sample size and no result below can
overturn it. If this study finds no weight predicts better than another, the fallback is
an equal 50/50 blend — never a return to rushing-only.

**This study tests exactly one thing: the weight `w`.**

```
dDOM_RB(w) = [ w · rdom + (1 − w) · dom ] × competition_multiplier(tpct)
```

`w = 1.00` is today's behaviour. `dom` is the existing receiving dominator, already
computed for every player by fetch-college.py. The competition multiplier is unchanged
(DDOM_SWING = 0.50) and is NOT under test here — it has its own provisional flag and
deserves its own study.

---

## 2. Prior exploratory work — full disclosure

An exploratory analysis was run on 22 Aug 2026 before this document. It is disclosed
because it is not independent of what follows, and because a reader deserves to know
which numbers were seen first.

- Sample: 58 RBs, being those with a qualifying final college season AND ≥4 real NFL
  games in some season 2023–2025. Everyone in it is on an NFL roster today.
- Outcome: best real NFL season PPG.
- Findings: all 21 weights from 0.00 to 1.00 were tried. In-sample peak was w = 0.30
  (rho 0.293) against w = 1.00 (rho 0.222). Under repeated half-splits, *tuning* w on a
  training half scored 0.199 on held-out data — worse than not tuning at all (0.220),
  which is overfitting. A fixed w = 0.50 scored 0.263 held-out and beat w = 1.00 on 86%
  of splits (78% on a draft-pick outcome).
- Interpretation carried forward: the CV curve is a broad hill, not a spike; the large
  gain is including receiving at all, and the weight within a wide middle band is worth
  only ~2–3 percentile points.

**Consequence for this study.** w = 0.50 and w = 0.30 have already been seen to do well
on a related outcome. This study's primary outcome (draft capital) is different, and its
sample is roughly 3–8× larger and includes players the exploratory sample structurally
could not see — those who were drafted and washed out. It is substantially, not fully,
independent. It is a calibration, not a clean replication, and will not be described as
one.

---

## 3. Sample

**Population:** every qualifying RB college season in `data/college-players-YYYY.json`,
using each player's FINAL qualifying season only — one row per player, so no player is
counted twice and rows are independent.

Qualifying is the existing `cfbQualifies` rule, unchanged: ≥6 games and ≥60 carries.

**Draft classes:** 2021–2026 (final college seasons 2020–2025) from files already on
disk. If the power check in §7 fails, extend backwards one draft class at a time by
backfilling college seasons via `fetch-college.py` with `CFBD_VISIBLE_FROM` left at
2024, so calibration seasons never surface on the live platform.

**Critically, undrafted players stay in.** Restricting to drafted players would condition
on the outcome and reproduce the exact selection problem that limited the exploratory
sample.

**Expected n, counted from the files on disk before any draft data was pulled:**

| | RBs |
|---|---|
| Distinct RBs with a qualifying final season, 2020–2025 | 450 |
| Less: final season 2025 (draft class 2026, unresolved) | −144 |
| Less: missing `rdom` or `dom` | −0 |
| **Primary-outcome sample** | **306** |

That is 5.3× the exploratory sample of 58, and unlike that sample it includes backs who
were drafted and washed out, and backs who went undrafted. The secondary-outcome sample
will be far smaller (the exploratory run found 58) because it requires real NFL games.

**Exclusions, fixed in advance:**
- No qualifying final season → excluded (cannot compute the metric).
- `rdom` or `dom` missing → excluded.
- Final college season 2025 → excluded from the primary outcome (draft class 2026 is not
  yet resolvable); retained for the secondary outcome only if real NFL games exist.

---

## 4. Outcomes

**Primary — draft capital.** Spearman rank correlation between `dDOM_RB(w)` and draft
capital, computed over all qualifying RBs in the population, with every undrafted player
tied at the bottom rank. Higher is better. Draft capital is used because it is available
for the entire population including busts, is measured once and cleanly, and carries no
NFL-opportunity noise. It measures what NFL evaluators concluded, which is a proxy for
talent and not the same thing as fantasy production — an acknowledged limitation.

**Secondary — NFL production.** Spearman rank correlation with best real NFL season PPG,
among players with ≥4 games in a season. This is the dynasty-relevant outcome but is
available only for survivors, so it is secondary and cannot on its own decide the weight.

The primary decides. The secondary is reported always, whatever it shows, and a
disagreement between the two is reported as a disagreement rather than resolved by
picking the friendlier one.

---

## 5. Weight grid

`w ∈ {0.00, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00}` — 11 values.

Deliberately coarse. A finer grid buys precision the sample cannot support and invites
exactly the noise-chasing the exploratory run demonstrated.

---

## 6. Selection rule — fixed before seeing results

1. Score every `w` by repeated 5-fold cross-validation, 200 repeats, on the primary
   outcome. Report the mean and standard error of held-out rho per `w`.
2. Find `w*`, the weight with the best mean held-out rho.
3. Apply the **one-standard-error rule**: from all `w` whose mean is within 1 SE of
   `w*`'s mean, select the one closest to 0.50. Ties break toward 0.50.

The 1-SE rule and the tie-break toward 0.50 are both regularisation, chosen in advance
because the exploratory run showed that taking the raw peak actively degraded held-out
performance. The intent is to land on a defensible round number unless the data clearly
insists otherwise.

**Rounding:** the selected weight ships as-is from the grid. No interpolation, no
second-decimal tuning.

---

## 7. Power check and ship gate

**Power check, run first and reported before the selection result:** the width of the
bootstrap 95% CI on held-out rho at w = 0.50. If that CI is wider than ±0.12, the sample
is declared underpowered to choose a weight. In that case the study ships **w = 0.50** as
an explicitly un-tuned default, records the power failure, and the weight question stays
open pending a backwards extension of the sample.

**Ship gate for a weight other than 0.50:** a non-0.50 weight ships only if it beats
w = 0.50 on held-out primary-outcome rho in ≥ 75% of 500 repeated half-splits. Otherwise
0.50 ships. The asymmetry is deliberate — 0.50 is the un-tuned default and a challenger
must earn its place.

**Sanity gate, must pass either way:** the selected weight must beat w = 1.00 (today's
rushing-only) on held-out primary rho in ≥ 60% of splits. If even that fails, something
is wrong with the join or the outcome and nothing ships until it is understood. This is a
plausibility check on the pipeline, not a re-litigation of §1.

---

## 8. What gets reported regardless of outcome

- n at every stage, including how many were dropped and why.
- The full CV curve across all 11 weights, not just the winner.
- Both outcomes, including a disagreement between them.
- The power check result.
- Which players move most under the selected weight, in both directions.
- If the result contradicts the exploratory finding, that is stated plainly rather than
  reconciled.

---

## 9. What this study does NOT license

- Changing DDOM_SWING (the competition multiplier). Still provisional, separate study.
- Changing the qualifying thresholds (≥6 games, ≥60 carries).
- Changing dDOM for QB, WR or TE.
- Changing the Scout ordering, which does not use dDOM at all.
- Any change to the NFL-side DELTA Score, projection or buy/sell call. College data is
  tracking-only and feeds none of them. Nothing here touches the accuracy ledger frozen
  on 6 September 2026.

---

## 10. Amendments

**Amendment 1 — 22 Aug 2026, BEFORE any confirmatory run.**
Section 6's one-standard-error rule is unchanged in intent, but the standard error is now
computed the classic way: the spread across the k CV folds divided by sqrt(k), not the
spread across every fold-score divided by the total count of them. The original form let
SE shrink toward zero as CV repeats rose, which narrowed the 1-SE band to nothing and
silently reduced the rule to "take the peak" — precisely the behaviour it exists to
prevent, and precisely the mistake that produced w = 0.30 in the exploratory run.
Found by the self-test, not by inspection.

**Amendment 2 — 22 Aug 2026, BEFORE any confirmatory run.**
Section 7's power check is replaced by two checks, because the original was invalid.
It measured the width of the bootstrap CI on rho at w = 0.50 and called a narrow CI
"powered". On data with no relationship at all, rho is reliably near zero and its CI is
narrow, so pure noise scored as WELL POWERED. The self-test planted a no-signal dataset
and the study confidently returned a weight, which is the failure this document exists to
make impossible. Replaced by:

- **Signal check** — the bootstrap CI on rho at w = 0.50 must exclude zero. If it does
  not, the metric bears no relationship to the outcome and no weight may be inferred.
- **Discrimination check** — the bootstrap CI on the difference rho(w*) − rho(0.50) must
  exclude zero. If it does not, the CV curve is flat within noise and 0.50 ships as an
  explicitly un-tuned default.

If either check fails, w = 0.50 ships and the weight question stays open. The ship gates
in section 7 (75% against 0.50, 60% against 1.00) are unchanged.

**Amendment 3 — 22 Aug 2026, after the first confirmatory run, reporting only.**
The discrimination check from Amendment 2 is marked NOT APPLICABLE when the empirical
best weight IS the default 0.50. In that case rho(w*) − rho(0.50) is identically zero,
the bootstrap CI collapses to [0, 0], and the check reports FAIL — labelling the study
underpowered when the data in fact showed strong signal and agreed with the default. The
check exists to stop a CHALLENGER being adopted on noise; with no challenger there is
nothing to test.

This changed no selected weight and no gate result — 0.50 ships either way. It changed
only the verdict text, from "underpowered, question stays open" to "the empirical best
and the pre-registered default are the same weight". Recorded here because it was made
after seeing a result, which is exactly the kind of change that must never be silent.

_Amendments 1 and 2 were made before the study touched real data. Amendment 3 was made
after, affects reporting only, and is flagged as such. All are recorded here rather than
edited into the sections above so the original design stays visible._
