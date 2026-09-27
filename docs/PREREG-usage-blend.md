# PRE-REGISTRATION — Does Usage Beat Points Early In The Season?

**Written:** 27 September 2026. No outcome has been looked at: the only runs were `--count`
(eligibility, no errors) and a crash test with every outcome replaced by random numbers (it proves the
code runs — nothing more; see Part 1, Amendment 2 — noise can "pass" a smoother predictor).
**Status:** locks on commit. Changes after the first run go in Amendments, with a reason.
**Script:** `scripts/usage-study.py` — `--count`, then `--run`, which refuses unless this file is
committed and unedited. Games, scoring and player IDs come from `scripts/blend-study.py`; rookie
baselines and their no-leak fitting rules from `scripts/blend-study-rookies.py`, both unchanged.

---

## 1. The Question

The live projection blends a player's **points per game so far** with his preseason number (K = 4
veterans, 2 thin history, 3 rookies). Points are noisy — one long touchdown swings a week. Usage
settles faster. **Does a player's usage so far predict his rest-of-season scoring better than his
points so far?**

---

## 2. The Contender

**xFP (usage-based points):** his targets and carries so far, each valued at what an average target or
carry at his position was worth over the **three previous seasons**, league-wide, in half PPR + TE
premium — then per game. Nothing from the season being predicted goes into the values.

- **Today's live blend:** `w × PPG so far + (1 − w) × preseason`, `w = G ÷ (G + K)`.
- **Usage blend:** `w × [(1 − v) × PPG so far + v × xFP so far] + (1 − w) × preseason`.

`v = 0` is exactly today's blend. **`v` is chosen once, on training seasons** (2018–2022, the average of
the five seasons' errors), from 0.0 to 1.0 in steps of 0.1; ties go to the smaller `v`. If `v = 0` wins
in training, the study ends there: usage adds nothing.

**Scope:** RB, WR, TE only — targets and carries do not describe how a quarterback scores. Checkpoints
after **Weeks 2, 3, 4 and 6**. Graded if 1+ game by the checkpoint and 4+ after. Players need a
preseason number: a drafted rookie (rookie table), or 1+ prior-season games (the Part 1 formula).
Undrafted rookies are excluded, as in Part 2.

---

## 3. The Pass Mark — All Four, Or Nothing Changes

On 2023–2025, graded once, the usage blend against today's blend:

1. **Size:** typical miss (RMSE, mean of the four checkpoint RMSEs) at least **2% lower**.
2. **Not a fluke:** paired shuffle test, p < 0.05, 2,000 shuffles, seed 20260927, one-sided, swapping the
   two predictions' errors per player-season. Two real predictions on the same players — not the
   market-form study's flawed design.
3. **Every held-out season:** better in 2023, 2024 and 2025 each.
4. **No position harmed:** no position with 30+ held-out player-seasons more than 1% worse.

**Stated in advance so it can be wrong:** usage should help most at Weeks 2–3 and fade by Week 6, and
most for rookies, whose preseason number knows least. Whether it clears 2% overall is genuinely open.

**Reported only:** results by group (veterans, thin history, rookies) and by checkpoint.

---

## 4. What Happens After

- **Pass:** the live in-season blend uses the usage mix at the chosen `v`, for RB/WR/TE. The engine needs
  each player's 2026 targets and carries (confirmed: `game-logs.json` rows carry `tgt` and `car` for
  every 2026 game) and the three-season values. Build agreed with the owner; before-and-after table; Engine Audit
  32/32; DELTA Scores unchanged.
- **Not shown:** today's blend stays.

---

## Pre-Lock Checks (27 September 2026)

| Check | Result |
|---|---|
| Values per target / per carry (2023) | RB 1.13 / 0.63 · WR 1.41 / 0.88 · TE 1.75 / 1.05 — sensible for half PPR + TE premium |
| Usage joined onto played games, 2023–24 RB/WR/TE | 58,855 targets + carries raw = 58,855 joined; no duplicated rows |
| Veterans vs Part 1 machinery, Weeks 3 and 6 | 4,433 of 4,433 identical (preseason, points so far, games) |
| Rookies vs Part 2 machinery, Weeks 3 and 6 | 709 of 709 identical (baseline, points so far) |
| `--run` refuses while this file is uncommitted | Refused |
| Full `--run` path, outcomes replaced by random numbers | Runs end to end — crash test only |

**Graded player-checkpoints** (printed by `--count`):

| Season | After Week 2 | After Week 3 | After Week 4 | After Week 6 |
|---|---|---|---|---|
| 2018 | 304 | 316 | 319 | 312 |
| 2019 | 315 | 318 | 317 | 311 |
| 2020 | 333 | 344 | 348 | 350 |
| 2021 | 337 | 345 | 354 | 351 |
| 2022 | 331 | 343 | 355 | 351 |
| **2023** | 335 | 346 | 354 | 357 |
| **2024** | 342 | 352 | 353 | 351 |
| **2025** | 325 | 338 | 349 | 346 |

Training 6,654 rows. Held out (bold) 4,148 rows from 1,122 player-seasons: WR 516, TE 312, RB 294;
veterans 903, rookies 158, thin history 61.

---

## Amendments

*(none)*
