# PRE-REGISTRATION — Does DELTA's In-Season Read Predict Where The Market Goes?

**Written:** 26 September 2026. No future price has been read: the only runs were `--count`
(eligibility; the script never loads next-season prices in that mode) and a crash test with
every future price replaced by random numbers (proves the code runs — nothing more).
**Status:** locks on commit. Changes after the first run go in Amendments, with a reason.
**Script:** `scripts/market-form-study.py` — `--count`, then `--run`, which refuses unless this
file is committed and unedited. DELTA's numbers come from `scripts/blend-study.py` and
`scripts/blend-study-rookies.py`, imported unchanged.

---

## 1. What This Decides

The in-season blend (Parts 1 and 2) makes DELTA's **projection** react to this season. It barely
touches **buy/sell calls**, because model value is the market price adjusted by small percentages
and reads the projection only through a tier bonus. Rookies read "no data" all season.

**The question:** when a player's early-season games move DELTA's projection, and the market's
price moves by a different amount, **who turns out right about his price by the next September?**
If DELTA's move adds real information, it earns a place in the calls, and this study sizes it. If
not, the calls stay as they are.

---

## 2. Prior Work — Full Disclosure

- **`docs/RESEARCH-market-independent-value.md` (Aug 2026):** DELTA's disagreements with the
  market did not predict price moves (+0.047, p = 0.216); usage was already in the price; mixing a
  production-based value into the market made it worse. **This is the strongest prior and it
  points against a pass.** What differs here: that test measured *level* disagreements at one
  September snapshot; this one measures *in-season re-ratings*, which the market may over- or
  under-react to. It is a different question, not a re-run with a new metric.
- **The blend studies (26 Sep):** the re-rating used here is the live blend (K 4 / 2 / 3).
- **Seen before locking:** snapshot dates, eligibility counts, and the validation checks below. No
  future price, error, or coefficient was computed.

---

## 3. The Measures

At the first DynastyProcess snapshot after Week 4, and after Week 8, of each season 2020–2025:

| Name | Plain English | Formula |
|---|---|---|
| **DELTA's move** `r_D` | How far DELTA's projection moved since preseason | `log(blend + 1) − log(preseason + 1)` |
| **Market's move** `r_M` | How far his price moved over the same stretch | `L(price now) − L(price before Week 1)` |
| **What happened** `f` | Where his price went by the next season | `L(price before next Week 1) − L(price now)` |

`L(v) = log(v + 100)`. A player missing from the next season's snapshot counts as price 0.

- **Prices:** DynastyProcess `files/values.csv` git history, `value_2qb` (superflex, DELTA's
  anchor), dated by `scrape_date`. Snapshots: the last before Week 1 (on or after 1 August), and the
  first after the last game of Week 4 / Week 8; none used if more than 10 days from its target.
- **Players join to nflverse by ID** through DynastyProcess's crosswalk (`fantasypros_id → gsis_id`).
- **Preseason and blend:** exactly the two blend studies: veterans (8+ prior games) K 4, thin
  history (1–7) K 2, drafted rookies K 3 against the rookie table (held-out seasons use the
  2015–2022 table; training seasons that table minus the season itself).
- **Graded:** QB/RB/WR/TE with a price before Week 1 and at the checkpoint (both above 0), a DELTA
  preseason number, and **at least one game played by the checkpoint** (otherwise DELTA has no read).

---

## 4. The Comparison

- **Market only:** `f ~ r_M + L(price now) + age + age² + position + checkpoint`
- **Market plus DELTA:** the same, plus `r_D`

Both fit on **2020–2022**, graded **once** on **2023–2025**.

---

## 5. The Pass Mark — All Five, Or Calls Do Not Change

1. **Size:** the typical miss (RMSE, mean of the two checkpoints) is **at least 2% lower** with DELTA.
2. **Not a fluke:** permutation p < 0.05 — DELTA's move shuffled within season × checkpoint ×
   position on the held-out rows, fitted coefficients fixed, 2,000 shuffles, seed 20260926,
   p = (shuffles at least as good + 1) ÷ 2,001.
3. **Right direction:** DELTA's coefficient is positive (the market later moves toward DELTA).
4. **Every held-out season:** improvement in 2023, 2024 and 2025 each.
5. **No position harmed:** no position with 30+ held-out player-seasons more than 1% worse.

**Three outcomes, named in advance:**

| Outcome | Meaning | What Happens |
|---|---|---|
| **Pass** (all five) | DELTA's in-season read predicts price moves, by a useful amount | A form term enters model value, sized by the fitted coefficient (§6) |
| **Real but small** (2, 3 and 4 hold, size under 2%) | The signal exists but is too small to act on by the platform's bar | Calls unchanged. Showing DELTA's form read as information is the owner's call |
| **Not shown** | No reliable signal | Calls unchanged. The market already handles in-season form |

**Stated in advance so it can be wrong:** the most likely result is "real but small" or "not
shown". A 2% improvement needs a correlation of roughly 0.2, and the August test found about 0.05.

**Reported only, never gated:** the partial correlation (comparable to August's +0.047);
improvement by group (veterans, thin history, rookies); a descriptive check of whether DELTA's
move relates to next-season points per game beyond the market.

---

## 6. What Ships On A Pass

A form term in model value: `× exp(β × r_D)`, with `β` the fitted coefficient and `r_D` from the
live engine (`proj` vs `projPre`). Rookies who have played get it in the rookie branch too, and
stop reading "no data" once they have a DELTA read. Build details with the owner's approval,
Engine Audit 32/32, DELTA Scores unchanged.

---

## 7. Not Tested Here

- **FantasyCalc** (trade-based) keeps no public history. DynastyProcess is expert consensus.
- DELTA's move uses the blend without the Start Profile penalty (blend alone and blend plus
  penalty were indistinguishable in Part 1).
- Situational multipliers, ripples, contract — not reconstructable for past seasons.

---

## Pre-Lock Checks (26 September 2026)

| Check | Result |
|---|---|
| Prices vs the raw DynastyProcess files | 3,370 of 3,370 identical |
| ID links: DynastyProcess name vs nflverse name | 712 of 729 identical; all 17 others the same person (e.g. Robby Anderson / Robbie Chosen, Tank Dell, an accent on Estimé) |
| DELTA's read vs the validated Part 1 machinery, same players and weeks | 3,207 of 3,207 veteran rows identical |
| `--run` refuses while this file is uncommitted | Refused |
| Full `--run` path, future prices replaced by random numbers | Runs end to end — crash test only |

**Snapshots:**

| Season | Before Week 1 | After Week 4 | After Week 8 | Next Season |
|---|---|---|---|---|
| 2020 | 2020-09-03 | 2020-10-08 | 2020-11-05 | 2021-09-03 |
| 2021 | 2021-09-03 | 2021-10-05 | 2021-11-05 | 2022-09-02 |
| 2022 | 2022-09-02 | 2022-10-07 | 2022-11-04 | 2023-09-01 |
| 2023 | 2023-09-01 | 2023-10-06 | 2023-11-03 | 2024-08-30 |
| 2024 | 2024-08-30 | 2024-10-04 | 2024-11-01 | 2025-08-29 |
| 2025 | 2025-08-29 | 2025-10-03 | 2025-10-31 | 2026-09-04 |

**Graded player-checkpoints** (printed by `--count`):

| Season | After Week 4 | After Week 8 |
|---|---|---|
| 2020 | 250 | 311 |
| 2021 | 293 | 311 |
| 2022 | 330 | 353 |
| **2023** | 366 | 398 |
| **2024** | 332 | 353 |
| **2025** | 316 | 335 |

Training 1,848 rows. Held out (bold) 2,100 rows from 1,097 player-seasons: WR 445, RB 293, TE 202,
QB 157; veterans 875, rookies 178, thin history 44.

---

## Amendments

*(none)*

## Result (26 September 2026) — NOT SHOWN. Calls unchanged.

Run once, `python3 scripts/market-form-study.py --run`, against this file as committed in `be322f3`
(sha256 prefix `1f641015858253c5`). Nothing above this section was changed after the run.

| Held-Out 2023–2025 (2,100 checkpoints) | Typical Miss, Log Price |
|---|---|
| Market only | 0.5851 |
| Market plus DELTA's move | 0.5845 |
| **Improvement** | **0.10%** (bar: 2%) |

| Gate | Result |
|---|---|
| 1. Size ≥ 2% | **FAIL** — 0.10% |
| 2. Permutation p < 0.05 | passed, p = 0.0005 — **but see the flaw below** |
| 3. Right direction | passed — coefficient +0.161 (the market later drifts slightly toward DELTA) |
| 4. Every held-out season | **FAIL** — 2023 +0.26%, 2024 +0.60%, **2025 −0.56%** |
| 5. No position worse than −1% | passed — QB +0.22%, RB +0.45%, WR −0.08%, TE −0.43% |

**Outcome by §5's table: "Not shown."** "Real but small" needed gates 2, 3 and 4; gate 4 failed.

**Flaw in gate 2, found on reading the result.** The shuffles replaced DELTA's move with shuffled
values while keeping the fitted coefficient, so every shuffle adds noise at that weight and makes the
forecast worse. That tests "better than a random nudge of the same size", not "better than adding
nothing", and it passes almost anything with a positive fit. The p-value overstates the evidence.
It does not change the outcome (gates 1 and 4 fail regardless). **Any future study using this
design must shuffle and refit, or test against a zero coefficient.**

**Reported only, never gated:** partial correlation +0.095 (August's level test: +0.047) ·
by group: veterans −0.13%, thin history −0.43%, **rookies +1.02%** (178 held-out player-seasons) ·
next-season PPG, in-sample and descriptive: 3.629 → 3.604 (0.7%).

**What this says:** the market does move a little toward DELTA's in-season read on average, but by
far too little to change a forecast, and not reliably from year to year. The market already prices
early-season form. The rookie number is the only one worth a second look, and it would need its own
pre-registration — it cannot be promoted from this run.
