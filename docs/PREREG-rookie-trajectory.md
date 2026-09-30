# PRE-REGISTRATION — Rookie Trajectory: Does "He Came On Late" Predict Year Two?

**Written:** 30 September 2026. No year-two outcome has been looked at: the only runs were `--count`
(rookie-year stats only) and two crash tests with made-up year-two outcomes — random (the study correctly
chose "no weight" and stopped) and outcomes built to follow the second half (it correctly found them).
Both prove the code runs — nothing more.
**Status:** locks on commit. **Script:** `scripts/trajectory-study.py`.

**Disclosure:** about 85 of these players were breakout rookies whose year-two scoring was seen in
`docs/PREREG-rookie-breakout.md` and `docs/PREREG-rookie-volume.md`. **Whether second-half rookie scoring
predicts year two has never been looked at for anyone.**

---

## 1. The Question

A common dynasty intuition: a rookie who "came on late" is better than his season average says (Rashee
Rice 2023: 10.9 full season, 13.3 in the second half; Jayden Reed 11.5 → 14.8; Bucky Irving 2024 13.1 →
15.4). Suggested by the outside review of 29 Sep. **Today DELTA starts a second-year player from his
full-season rookie average** (with one season, the engine's season weights cancel).

---

## 2. The Test

- **Today:** year-two forecast = rookie full-season points per game.
- **Candidate:** `λ × second-half PPG + (1 − λ) × full-season PPG`. **Second half** = the later half of the
  games he played (an odd game goes to the first half).
- **λ chosen once, on classes 1999–2016** (the average error over those eighteen classes; 0.0 to 1.0 by 0.1;
  ties to the smaller). **λ = 0 is exactly today** — if it wins in training, the study ends there.
- **Graded once on classes 2017–2024.**
- **Players:** drafted QB/RB/WR/TE with **8+ rookie games** (so each half has at least 4) and **4+ games in
  year two** (fewer: excluded and counted). **846 rookies: 529 training, 317 test.**
- **Games** = games with a recorded stat, for every era (no snap counts before 2012 — one rule
  throughout); scoring half PPR + TE premium (the blend study's function).

## 3. The Pass Mark — All Four

1. **Size:** typical miss (RMSE) at least **2% lower**.
2. **Not a fluke:** paired shuffle test per player, p < 0.05, 2,000 shuffles, seed 20260930, one-sided.
3. **Most classes:** better in **at least 6 of the 8** test classes (about 40 players each).
4. **No position harmed:** none with 30+ test players more than 1% worse.

**Stated in advance so it can be wrong:** **not shown.** Half a season is noisy, and the full season holds
twice the games; the "came on late" story may be real for some players without helping on average.

**Reported only:** training error at every λ; second-half-only (λ = 1) on the test classes.

---

## 4. What Happens After

- **Pass:** second-year players' starting number uses the chosen mix, computed from last season's game logs
  (which the engine already loads). Before-and-after, Engine Audit 32/32, build agreed with the owner first.
- **Not shown:** second-year players keep their full-season average.

---

## Pre-Lock Checks (30 September 2026)

| Check | Result |
|---|---|
| Examples (rookie-year stats only) | Rice 10.9 → 13.3 · Reed 11.5 → 14.8 · Irving 13.1 → 15.4 · Bowers 15.5 → 16.7 · Brian Thomas Jr. 13.9 → 14.6 · Nacua 14.5 → 13.7 |
| Counts | 846 (WR 361, RB 267, TE 140, QB 78); training 529, test 317 |
| Crash test, random outcomes | λ = 0 chosen; stopped — no false pass |
| Crash test, outcomes built to follow the second half | λ = 1.0 chosen; grading path runs |
| `--run` refuses while this file is uncommitted | Refused |

---

## Amendments

*(none)*
