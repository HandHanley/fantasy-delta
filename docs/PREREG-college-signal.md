# PRE-REGISTRATION — Does College Production Predict Rookies Beyond Draft Slot? (With A dDOM Sub-Test)

**Written:** 29 September 2026. No outcome has been looked at in this study: the only runs were
`--count` (links and counts), a check that the study's dDOM equals the site's, and a crash test with every
rookie outcome replaced by random numbers (proves the code runs — nothing more).
**Status:** locks on commit. **Scripts:** `scripts/college-signal-study.py`, which runs DELTA's live dDOM
code through `scripts/ddom-dump.js`.

---

## 1. Why This Question

Four rookie studies (28–29 Sep) found the dynasty market prices draft slot, rookie production and the
sophomore slump about right. The market leans heavily on **draft slot**. If DELTA has a rookie edge, it
must come from information the market weighs less — DELTA's **own college data**.

**What has been seen before, disclosed:** (1) the July "college signal" work tested which prospects
*become NFL assets* (star rating and conference beat raw production); (2) the August dDOM calibration
found dDOM lines up with NFL outcomes a little better than the raw metric (n = 259; its write-up,
`DDOM-CALIBRATION.md`, is not in the repo — a documentation gap); (3) dDOM correlates 0.41 with draft
capital. **None asked whether college production adds anything *beyond* draft slot.** The players overlap
those earlier samples — DELTA's college data starts in 2020, so no fresh classes exist.

---

## 2. The Test

- **Rookies:** drafted QB/RB/WR/TE, **classes 2021–2025**, linked by name (and position) to their **final
  qualified college season** (6+ games and the dDOM volume floor), and with at least one NFL rookie game.
  **289 players.** Not covered, disclosed: 69 of 396 have no qualified final season — **2020 COVID
  opt-outs** (Ja'Marr Chase, Rashod Bateman, Nico Collins), **FCS players** (Trey Lance, Christian Watson,
  Tucker Kraft — the data is FBS-only), **injury-shortened final years** (George Pickens, Rondale Moore,
  Luke Musgrave), and name mismatches ("Tank" / Nathaniel Dell). The result speaks for linked rookies only.
- **Outcome:** rookie points per game over the games he played — exactly the rookie table's definition
  (half PPR + TE premium).
- **Baseline:** DELTA's rookie table — median rookie PPG by position × draft tier — fitted on every rookie
  season 2015–2025 **except the class being predicted**.
- **dDOM version:** baseline × (1 + b × (dDOM percentile ÷ 100 − 0.5)). One `b` for all positions, fitted on
  the other four classes; each class is predicted once (leave one class out).
- **dDOM is DELTA's live code:** `ddom-dump.js` runs `index.html`'s own `cfbDDOM` on each season — 469 of
  469 identical to the published college index.

---

## 3. The Pass Marks

**Primary — does dDOM add anything beyond draft slot?** dDOM version vs baseline, all four:
1. **Size:** typical miss (RMSE) at least **2% lower**.
2. **Not a fluke:** paired shuffle test per player, p < 0.05, 2,000 shuffles, seed 20260929, one-sided.
3. **Most classes:** better in **at least 4 of the 5** classes (40–70 players each).
4. **No position harmed:** no position with 30+ players more than 1% worse.

**Sub-test — does dDOM's competition adjustment help?** The same model built on the **raw** metric's
percentile (receiving dominator, the RB blend, QB ANY/A — no team-talent scaling), compared with dDOM:
bootstrap 95% range of (raw typical miss − dDOM typical miss), 2,000 resamples.

| Range | Verdict |
|---|---|
| entirely above zero | **dDOM beats the raw dominator** |
| entirely below zero | **the raw dominator beats dDOM** |
| crosses zero | **no clear difference** |

**Stated in advance so it can be wrong:** primary **not shown** — draft slot already carries most of
what college production says (they correlate 0.41), and 289 rookies is modest. Sub-test: no clear
difference.

**Reported only:** the raw metric's own lift over the baseline; the fitted `b`; results by class and
position.

---

## 4. What Happens After

- **Primary passes:** a design for **dDOM-adjusted rookie projections** (the engine's rookie baseline ×
  the dDOM factor), agreed with the owner before it's built; before-and-after; Engine Audit 32/32. It would
  also be the first evidence of a DELTA rookie edge the market may underweight — worth a market test next.
- **Not shown:** rookie projections stay on draft slot, and dDOM stays display-only, as today.

---

## Pre-Lock Checks (29 September 2026)

| Check | Result |
|---|---|
| dDOM from the live code vs the published college index | 469 of 469 identical |
| College link (drafted 2021–25) | 327 of 396 linked (83%); rounds 1–7 between 71% and 93% |
| Graded after the "played a rookie game" rule | 289: 2021 42 · 2022 57 · 2023 60 · 2024 61 · 2025 69; WR 121 · RB 81 · TE 50 · QB 37 |
| `--run` refuses while this file is uncommitted | Refused |
| Full `--run` path, outcomes replaced by random numbers | Runs end to end — crash test only |

---

## Amendments

*(none)*
