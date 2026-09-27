# PRE-REGISTRATION — Does The Start Profile Penalty Earn Its Place In The Preseason Projection?

**Written:** 27 September 2026. No outcome has been looked at: the only runs were `--count`
(eligibility, no errors), crash tests with every outcome replaced by random numbers (they prove the code
runs — nothing more), and a count of how often the ceiling changes a projection (predictions only, no
outcomes).
**Status:** locks on commit. Changes after the first run go in Amendments, with a reason.
**Script:** `scripts/startprofile-study.py` — `--count`, then `--run`, which refuses unless this file is
committed and unedited.

---

## 1. The Two Levers, And Why Only One Is On Trial

Both read the Start Profile (last 34 played games; 20+ needed) and have never been tested preseason:

- **Penalty ("RULE 4" in `calcProj`):** −9/−6/−3/−1% when Miss % is above 65/55/45/40, eased +3/+1%
  when Elite % is above 30/20 (never above 0). The projection takes half.
- **Ceiling ("FIX 2"):** Miss % above 65 caps the projection at 0.92 × the position ceiling; above 55, at
  1.05 × (position ceiling QB 22.0, TE 11.5, RB/WR 12.5).

**The ceiling cannot be tested and stays as it is.** On this study's projection it changes **0 of 2,134**
player-seasons: a player who misses the usable-starter line 55%+ of the time already projects below the
cap. It can only bite when the engine's other adjustments (team system, QB quality) push a projection
up, and those cannot be rebuilt for past seasons. On the live site on 27 Sep it holds back **1 of 137**
players in its zone (Christian Watson, 13.13).

**So one question:** does the penalty make the preseason projection better, or should it go?

**Prior disclosure:** the 10 Aug 2026 Miss % study failed; in-season (Part 1) blend-with-penalty and
blend-without tied.

---

## 2. The Test

- **Today:** starting number (the engine's rule, verified 315/315) × the missed-time multiplier shipped
  27 Sep × (1 + 0.5 × penalty), then the (inert) ceiling.
- **Penalty off:** the same without the penalty. Fixed in advance — no choosing among versions.
- **Graded:** QB/RB/WR/TE with 20+ games in the Start Profile going into the season (the only players
  the penalty can touch), 8+ prior-season games and 6+ games in the season predicted. Start Profile =
  the last 34 played games before the season, half PPR + TE premium lines, the blend study's maths
  (verified 305/305 against the engine's own profiles).
- **Data:** nflverse 2015–2025; training 2018–2022 (reported only); **held out 2023–2025, graded once.**
- **Simplification, disclosed:** the live engine applies the penalty inside a capped sum of adjustments;
  here it is a plain multiplier.

---

## 3. The Pass Mark — All Four, Or The Penalty Stays

"Penalty off" against today on 2023–2025:

1. **Size:** typical miss (RMSE) at least **2% lower**.
2. **Not a fluke:** paired shuffle test per player, p < 0.05, 2,000 shuffles, seed 20260927, one-sided.
3. **Every held-out season:** better in 2023, 2024 and 2025 each.
4. **No position harmed:** no position with 30+ cases more than 1% worse.

**Stated in advance so it can be wrong:** most likely "not shown" either way — the penalty is small
(half of 1–9%) and touches players whose projections are already modest.

---

## 4. What Happens After

- **Pass (penalty off is clearly better):** RULE 4 comes out of `calcProj` — preseason, and in-season too,
  since Part 1 found it added nothing on top of the blend. Model value's own volatility term
  (`d_vol_mv`) is a separate lever and is not affected. Before-and-after; Engine Audit 32/32.
- **Not shown:** the penalty stays, as the platform's rule requires. Both findings are recorded.

---

## Pre-Lock Checks (27 September 2026)

| Check | Result |
|---|---|
| Penalty maths vs the engine's RULE 4 | Same thresholds and rounding; Start Profile verified 305/305 in Part 1 |
| Ceiling on the study's projection | Changes 0 of 2,134 player-seasons (predictions only) |
| Ceiling on the live site | Binds for 1 of 137 players in its zone |
| `--run` refuses while this file is uncommitted | Refused |
| Full `--run` path, outcomes replaced by random numbers | Runs end to end — crash test only |

**Graded player-seasons** (printed by `--count`): 2018 243 · 2019 235 · 2020 253 · 2021 291 ·
2022 274 · **2023 273 · 2024 278 · 2025 287**. Training 1,296; held out 838 from 420 players
(WR 347, TE 217, RB 180, QB 94). The penalty is active for 689 of the 838.

---

## Amendments

*(none)*
