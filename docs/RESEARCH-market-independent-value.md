# Market-independent valuation — research record

**Status: CLOSED. Candidate rejected. Nothing shipped.**
Conducted 17–18 Aug 2026. Consolidates seven working documents into one record for `docs/`.

**Question asked:** can DELTA produce a dynasty model value that is not anchored to FantasyCalc, and that is more accurate than the market?

**Answer:** a market-blind value is buildable and beats DELTA's own projection basis, but it loses to expert consensus in every year tested, and its disagreements with the market do not predict where prices move. The market-anchored design is vindicated.

---

## 1. What was built and tested

A discounted points-over-replacement model: projected PPG carried forward across a multi-year horizon, with future outcomes drawn from historical distributions conditioned on age (veterans) or draft capital (young players). No market input anywhere.

Data: nflverse 2000–2025, half PPR + TE premium. Market history from DynastyProcess's git archive (350 commits back to April 2019), which yields a September snapshot every year 2019–2024.

## 2. Findings that stand on their own

These are measurements, independent of whether the value model worked.

### 2.1 Aging is an availability effect, not a rate effect

Cohort of 4,291 contributor-seasons, tracked five years forward, **players who are gone counted as zero** — the survivorship control the earlier old-age refit lacked.

| | survives one year | rate **if he plays** |
|---|---|---|
| QB 34–40 | 0.60 | **0.98** |
| RB 30–35 | 0.60 | **0.84** |
| WR 32–38 | 0.66 | **0.86** |
| TE 31–33 | 0.66 | **0.88** |

The right-hand column sits between **0.84 and 1.12 at every age and position**. All the movement is in survival.

**Why this matters to DELTA:** the decline slopes in `AC` are steeper than the raw data suggests, and were kept that way deliberately in the August backtest because the sample was survivor-biased. This explains why that was correct — the steepness is doing attrition's work. **Do not flatten those slopes toward survivor-conditional rates in a future refit.** That is the trap this study exists to mark.

⚠️ The two columns are only meaningful together. "Rate if he plays" is ≈1.0 *because* the players who fell off are excluded from it. Quoted alone it would say age doesn't matter, which is the opposite of the finding.

### 2.2 Draft capital predicts breakout

1,586 drafted skill players 2000–2020, framed on the **draft class** so players who never took a snap count as zeros.

Probability of ever reaching startable production in years 1–5: top-10 QB **81%**, Rd 1 RB **70%**, top-10 WR **71%**, Rd 2 WR **43%**, Day 3 WR **7%**. Peak arrives in year 2–3, never year 1.

The distribution matters more than the mean: a Day 3 receiver averages 3.3 PPG and medians 1.7, but one in ten peaks at 9.2. These are lottery tickets and the mean describes none of them.

**Status:** largely confirms the existing rookie-tier work. The new part — the multi-year path and P(startable) — is display context for a rookie card, not a scoring input.

### 2.3 K = 24 games — the blend point

Fitted on 5,058 player-year observations. Predict a young player's next season as `w × observed + (1−w) × capital prior`, with `w = G/(G+K)`.

| model | RMSE |
|---|---|
| observed production only | 4.748 |
| draft-capital prior only | 4.620 |
| **blended, K = 24** | **4.177** |

About a season and a half of playing time before a young player's own production should outweigh where he was drafted. Flat between K = 20 and 30, so not a knife-edge. **Beats both pure strategies**, which is the useful part — neither signal is sufficient alone.

**This is the one finding with a real path into the engine.** `dsOpportunity` currently blends draft capital using a hard rule (≤2 years experience). K=24 replaces that cliff with a fitted continuous weight. It is a scoring change, so it must clear the ship gate (≥2% RMSE lift, permutation p<0.05) and belongs after the freeze.

### 2.4 DELTA's 3/2/1 weighting is roughly unbiased

Measuring actual PPG against the projection basis, on a cohort defined by season *t−1* only: mean ratio **0.97** for WR 24–26. Validation, no change required, and now a defensible claim on the methodology page rather than an assumption.

## 3. Why the value model failed

Three construction errors were found and fixed before the model was fairly tested. Recording them because each produced plausible-looking output.

1. **Phantom future years.** A ratio-form age multiplier cancelled the decline *level*, floating aging backs upward — James Conner ranked 119 places above market. Fixed by using measured retention that already includes attrition.
2. **Convexity, rookies.** The sketch computed `max(0, E[PPG] − replacement)` instead of `E[max(0, PPG − replacement)]`. Because the average drafted receiver is a bust, **every WR tier including top-ten picks priced at exactly zero.** Correcting it separated the tiers cleanly — a top-10 QB went from 0.81 to 12.45.
3. **Convexity, veterans.** The same error on the current season. **281 of 381 players — 74% — had a projection below replacement and were worth precisely zero, indistinguishable from each other.** After the fix, 26.

A fourth error was methodological: coarse age bands created a staircase where a 26- and 27-year-old leapfrogged for no reason. Replacing them with a continuous 2-year neighbourhood was the single change that turned a failing model into a passing one.

Also caught mid-run: a selection bug that conditioned on the outcome and produced a mean ratio of 1.75 ("the average young receiver beats his projection by 75%" — impossible for a real projection), and two harness bugs that silently priced every player as a Day 3 pick.

## 4. Validation, then defeat

### It beat DELTA's own baselines

Rolling-origin, four non-overlapping windows, continuous-age construction:

| window | basis | prev PPG | **kernel** | gate |
|---|---|---|---|---|
| test 2009–11 | 0.504 | 0.508 | **0.613** | PASS |
| test 2012–14 | 0.531 | 0.556 | **0.567** | fail (CI clips zero) |
| test 2015–17 | 0.486 | 0.491 | **0.567** | PASS |
| test 2018–20 | 0.521 | 0.557 | **0.638** | PASS |

Robust to bandwidth (flat from 1.0 to 3.0). **Driven by WR**, positive in all four windows. **QB negative in three of four and should be excluded** — see §5.

### It lost to the market

Against real September snapshots, with age distributions fitted only on cohorts whose forward window closed before the snapshot date:

| anchor | n | basis | **market** | kernel | paired |
|---|---|---|---|---|---|
| 2019 | 202 | 0.526 | **0.732** | 0.609 | market wins |
| 2020 | 194 | 0.555 | **0.784** | 0.642 | market wins |
| 2021 | 183 | 0.586 | **0.742** | 0.632 | market wins |

All intervals exclude zero. Stable across 1, 3, 5 and 8-season horizons — and the market's edge **grows** with the horizon.

**The finding that closes it:** blending the model into the market makes the market *worse*, monotonically (2020: 0.784 → 0.769 at 25% → 0.741 at 50%). If the model held anything the market lacked, a small weight would help. It is a noisier view of the same information.

⚠️ The comparator is expert consensus, not traded prices — DynastyProcess value is a monotone transform of FantasyPros ECR (Spearman 1.0000). "Beats FantasyCalc specifically" remains formally untested; FantasyCalc keeps no public history.

### Its disagreements did not pay

The narrower and more product-relevant test — where the model dissents, does the market later move toward it? Four consecutive snapshot pairs, pooled: **+0.047, 95% CI [−0.027, +0.120], p = 0.216.** Not significant. In 2023→24 the twenty players the model liked most fell 14 places on average.

## 5. The QB result

Steve's hypothesis: only 32 starting jobs, franchise quarterbacks hold them for a decade, so most young QBs are auditions that fail. Youth at QB should therefore mean high variance, not reliable upside.

**Confirmed:**

| QB age | mean | **median** | bust rate | still playing at +5 |
|---|---|---|---|---|
| 21–25 | 119 | **24** | 39% | 42% |
| 26–29 | 121 | **62** | 31% | **49%** |

Same mean, less than half the median, higher bust rate, *lower* five-year survival. Being young at QB means you haven't won the job yet. Contrast WR, where the youngest band is best on every measure and declines monotonically.

Age at receiver is straightforwardly good. Age at quarterback is a proxy for job security and peaks at 26–29. A monotone age adjustment pushes the wrong way over the first half of that curve, which is why it fails there.

## 6. Opportunity is already priced

Separate pre-registered test. Signal: share of team targets + carries in the season before the snapshot. Controls: market rank **and** the production basis. 846 player-anchors, 2019–2023, RB/WR/TE.

| | partial r | p |
|---|---|---|
| raw | **+0.439** | 0.0000 |
| controlling market | +0.046 | 0.177 |
| controlling market + basis | **+0.024** | 0.489 |

Opportunity is strongly related to future production, and essentially all of it is already in the price. Secondary test (does it predict market movement) is **−0.050**.

⚠️ WR came out +0.093 (p=0.064) and TE +0.129 (p=0.097). Both **fail** the pre-registered gate, three positions were tested, and the secondary test points the other way. These are not a positive finding and must not be written up as one. A revisit is a new study with fresh pre-registration and more anchors.

**This does not mean the opportunity axis is useless.** It has two jobs: providing edge over the market (tested, no) and powering the deliberately market-blind DELTA Score plus making scores explainable (untouched, still earns its place).

## 7. What remains genuinely open

- **Contract.** Plausibly *less* priced than opportunity — analysts discuss usage constantly and contract years rarely. **Not testable retrospectively**: OverTheCap keeps no public archive and nflverse carries nothing. Only the accuracy ledger can answer it.
- **System.** PROE reconstructs to 2006; motion% and TE2 alignment need FTN charting and don't exist before 2022. Consistent with the standing note to revisit ~2029–30.
- **Power.** With ~1,100 observations the smallest detectable partial correlation is **0.084** (0.104 across six corrected tests). A real dynasty edge could plausibly be smaller than that and invisible here. Any null from this panel should be read as "not detectable at this sample size," not "absent."

## 8. Do-not-retry

- **Coarse age-band multipliers as a ranking device.** Measured out-of-sample, they lose to the raw basis at every position. Continuous age is the fix, and it works — but the banded form is dead.
- **The ratio-form age multiplier.** Cancels the decline level and floats aging backs upward. Confirmed twice now.
- **Flattening the `AC` decline slopes toward survivor-conditional rates.** They are steep on purpose; see §2.1.
- **Re-running §4 or §6 with a different truth metric hoping for a better number.** Three metrics, four horizons and one pre-specified stratum have been tried; all agree.
- **A market-blind value built from production and age alone.** Beaten by consensus in three independent years, at every position, at every horizon.

## 9. What this does not say

It does **not** say DELTA is inaccurate. `mvAssetRaw` is market-anchored and its ranking correlates **0.996** with the market, so DELTA inherits the market's accuracy rather than competing with it — the market scored 0.73–0.78 in the historical test.

What has no evidence behind it is the stronger claim: that DELTA's disagreements with the market are *profitable*. The closest available proxy for that came back null (§4). But the proxy used production and age only, while DELTA's verdict also carries system, contract, ripple and opportunity — and contract has never been tested by anyone.

That question is settled prospectively or not at all, which is what the 6 September freeze and the February 2027 ledger are for.

⚠️ Nothing from this thread was wired into the engine. No shipped behaviour changed. The only candidate change to emerge is K=24 (§2.3), which must clear the ship gate after the freeze.
