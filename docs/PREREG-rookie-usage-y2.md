# PRE-REGISTRATION — Does A Rookie's Early Playing Time Tell Us His Year Two?

**Written:** 10 October 2026, at the owner's request ("we're four games in — can anything give an indication on
rookies?"). No year-two points have been read: the only runs were `--count` (eligibility: it counts year-two
GAMES, never points), a hand-check of three rookies' early-season inputs, and `--crash` (every year-two outcome
replaced by random numbers — proves the code runs, nothing more).
**Status:** locks on commit. Changes after the first run go in Amendments, with a reason.
**Script:** `scripts/rookie-usage-y2-study.py` — `--count`, `--crash`, then `--run`, which refuses unless this file
is committed and unedited. Games, scoring, IDs, the draft-slot table recipe and the lock come from
`scripts/blend-study.py` and `scripts/blend-study-rookies.py`, imported unchanged; xFP follows
`scripts/usage-study.py` exactly.

---

## 1. Why

Rookies carry a group-level Hold (shipped 10 Oct, `e6e98c6`): seven rookie studies found the market prices them
about right, and DELTA has no individual read. Two earlier studies left a rookie-only hint, both reported only:
usage vs points for the **rest of the season** (+2.4%, `PREREG-usage-blend.md`) and in-season form vs **price**
(+1.02%, `PREREG-market-form.md`). Neither can be promoted from its own run.

**The owner asked for the modern era.** The 2013–2017 classes were proposed first (unseen for usage) and rejected
as a different era. So this study asks a **new question on recent classes**: not the rest of this season, but
**year two** — the dynasty question.

## 2. The Question

After Week 4 (and Week 8) of a drafted RB/WR/TE's rookie season, does his **playing time so far** — targets and
carries, valued as points — tell us his **year-two points per game** better than DELTA's rookie projection does
today?

## 3. The Numbers

| Name | Plain English | Formula |
|---|---|---|
| **Today** | DELTA's live rookie projection at the checkpoint | `w × PPG so far + (1 − w) × draft-slot baseline`, `w = G ÷ (G + 3)` |
| **Playing time** | The same, with points so far partly replaced by usage | `w × [(1 − v) × PPG so far + v × xFP so far] + (1 − w) × baseline` |
| **xFP** | What his targets and carries are usually worth | each target and carry valued at the league-wide average for his position over the **three previous seasons**, half PPR + TE premium, per game |
| **Outcome** | What happened | his **year-two PPG**, half PPR + TE premium, if he played **4+ games** that season |

- **Draft-slot baseline:** the live `ROOKIE_PPG` recipe (median rookie-season PPG by position × draft tier, rows
  non-increasing), **refit without the class being predicted**, from rookie seasons 2015–2024. It uses
  rookie-season points only, never year two.
- `v = 0` is exactly today's projection.

## 4. Fitting And Grading

- **`v` chosen once on the 2018–2021 classes** (172 rookies): the mean over those four classes of the
  checkpoint-averaged RMSE, `v` from 0.0 to 1.0 by 0.1, ties to the smaller `v`. **If `v = 0` wins, the study ends:
  playing time adds nothing.**
- **Graded once on the 2022–2024 classes** (140 rookies: WR 69, RB 37, TE 34). The 2024 class's year two is the
  2025 season, complete.
- **Era check, reported only:** the 2015–2017 classes (121 rookies) at the chosen `v`. It can never pass or fail
  anything.

Graded rookies (by `--count`, after Week 4 / after Week 8): 2018 42/45 · 2019 34/37 · 2020 39/44 · 2021 42/46 ·
**2022 36/44 · 2023 50/53 · 2024 35/43**.

## 5. Pass Marks — All Four, Or Nothing Changes

1. **Size:** test RMSE (mean of the two checkpoints) at least **2% lower**.
2. **Not a fluke:** permutation p < 0.05. For each test rookie, randomly swap which forecast is "today" and which is
   "playing time" (2,000 swaps, seed 20261010, p = (swaps at least as good + 1) ÷ 2,001). This tests improvement
   against zero — the fix the market-form study's flaw note asked for.
3. **Every test class:** better in 2022, 2023 and 2024 each.
4. **No position harmed:** no position with 30+ test rookies more than 1% worse.

**Known weakness, stated before the run:** the crash test (random outcomes) chose `v = 0.2` and passed gate 2
(p = 0.01) while failing gate 1 (+0.3%). A smoother forecast can beat noise slightly in RMSE, so gate 2 alone proves
little here; **gates 1 and 3 carry the decision.**

**Stated in advance:** the most likely result is **not shown**. 140 test rookies is small, and the closest earlier
study (rookie trajectory, same outcome) found nothing.

## 6. What Each Result Means

| Result | What Changes |
|---|---|
| **Pass** | DELTA gets its first tested individual read on a rookie's future: his playing-time projection for year two, shown on rookie cards with the owner's approval. **Still not a buy/sell call** — a call says the price is wrong, and that needs a price test (the forward test on the 2026 class). |
| **Not shown** | The rookie Hold stays. This lead is closed on these classes. |

## 7. Prior Looks At These Classes — Full Disclosure

- **Rookie trajectory** (`PREREG-rookie-trajectory.md`, 30 Sep): graded classes 2017–2024 on **year-two PPG**,
  testing second-half vs full-season rookie points. Not shown. **Same outcome, same classes, different predictor**
  (points, not usage). Its result is known; this study's predictor is not.
- **Rookie breakout, Study 2** (`PREREG-rookie-breakout.md`, classes 2015–2024): full-season volume vs **price
  change**; high-volume breakouts lost more value. Different outcome (price), full-season volume.
- **Usage blend** (`PREREG-usage-blend.md`, seasons 2018–2025): usage vs **rest-of-season** points; rookies +2.4%,
  reported only. Different outcome.
- No study has related **early-season usage** to **year-two points** on any class.

## 8. Not Tested Here

Quarterbacks (targets and carries do not describe how a quarterback scores), undrafted rookies, snap share on its
own, route participation, players with fewer than 4 year-two games (a rookie who washed out is not graded — this
study is about how much a player who sticks will score, not whether he sticks).

---

## Amendments

*(none)*

## Result (10 October 2026) — NOT SHOWN. The study ends at the training step.

Run once, `python3 scripts/rookie-usage-y2-study.py --run`, against this file as committed in `a90cdfe`
(sha256 prefix `4596f4acbaddae23`). Nothing above this section was changed after the run.

**Chosen on training: v = 0.** Per §4, the study ends there and the test classes were never graded.

| v (share of "points so far" replaced by playing time) | Training error, year-two PPG (2018–2021 classes) |
|---|---|
| 0.0 (today's rookie projection) | **3.380** |
| 0.2 | 3.398 |
| 0.5 | 3.450 |
| 1.0 (playing time only) | 3.605 |

Every step toward playing time made the year-two forecast **worse**, steadily, with no dip anywhere on the grid.

**What it says:** for a rookie who sticks into year two, his early points already carry what his early targets and
carries say about his year two, and more. Playing time is not a hidden signal the points miss. The rookie Hold stays;
this lead is closed on the 2018–2021 classes, and the 2022–2024 classes remain unseen for this question.
