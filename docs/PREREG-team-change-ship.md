# PRE-REGISTRATION — A Team-Change Adjustment: Ship Test

**Written:** 27 September 2026. **Disclosure:** three measurements on these same seasons have been seen
(`docs/PREREG-team-change.md`, `-age.md`, `-top150.md`): movers score about 16–17% below their own
history relative to stayers, at every age, including the top 150; the engine allows about 7–9%. This
test checks the effect holds **out of sample** (fit on 2018–2022, graded on 2023–2025) before anything
ships. The only runs were `--count` (no outcomes) and a crash test with every outcome replaced by random
numbers (proves the code runs — nothing more).
**Status:** locks on commit. **Script:** `scripts/teamchange-ship-study.py`, built on the locked
`scripts/teamchange-study.py` (teams, eligibility, starting number and fit imported unchanged).

---

## 1. The Owner's Decision (27 Sep 2026)

After the three measurements, the owner approved a **modest** team-change adjustment that closes only
the part of the gap DELTA doesn't already cover — keeping the engine's existing **directional** team
adjustments, so a player moving into a strong situation still gets his boost.

---

## 2. The Test — Built So It Cannot Pass By Accident

The plain starting number runs high for everyone, so "shrink movers" would beat "don't" even if moving
meant nothing. So **both sides are calibrated on training stayers**:

- **Baseline:** a mover forecast like a stayer — starting number × `m_S` (stayers' best-fit multiplier,
  2018–2022).
- **Candidate:** a mover gets the movers' own correction — × `m_S` × `r`, where `r = m_C ÷ m_S` from
  2018–2022.

Graded **once on the 265 movers of 2023–2025**. The only thing the candidate knows that the baseline
doesn't is that he changed teams.

**Pass mark — all four:**
1. **Size:** typical miss (RMSE) at least **2% lower**.
2. **Not a fluke:** paired shuffle test per player, p < 0.05, 2,000 shuffles, seed 20260927, one-sided.
3. **Every held-out season:** better in 2023, 2024 and 2025 each.
4. **No position harmed:** no position with 30+ held-out movers more than 1% worse.

---

## 3. What Ships If It Passes

**Size, by formula fixed now:** `extra = min(1, r_all ÷ (0.823 ÷ 0.886))`, where `r_all` is the movers ÷
stayers multiplier over all eight seasons and 0.823 ÷ 0.886 is the engine's existing extra caution
(recorded 27 Sep). It can only shrink projections, never boost them. From the measurements already
seen, it should land near ×0.90.

**The engine's rule — matching the study's definition of a move:** a veteran with 2025 games whose
**2025 main team** (most games, from `game-logs.json`; JAX = JAC, LA = LAR) differs from **the team in
his first 2026 game** (or his current team if he hasn't played yet). Offseason moves only: a player
traded **mid-season** is not caught, because this test says nothing about mid-season trades. Rookies are
never affected. Applied to the starting number, outside the adjustment cap, beside the missed-time
multiplier. DELTA Scores are not touched. Before-and-after table; Engine Audit 32/32. It rolls to the
right seasons automatically at the offseason roll (it compares `SEASON_YEAR − 1` with `SEASON_YEAR`).

**If it fails:** nothing changes, and the three measurements stand as recorded.

---

## Pre-Lock Checks (27 September 2026)

| Check | Result |
|---|---|
| Machinery | Imported unchanged from the locked team-change study |
| Live game logs carry each game's team (`tm`) | Yes |
| `--run` refuses while this file is uncommitted | Refused |
| Full `--run` path, outcomes replaced by random numbers | Runs end to end — crash test only |

**Counts** (printed by `--count`): training 400 movers / 1,220 stayers; held-out movers 265 (WR 116,
TE 64, RB 55, QB 30).

---

## Amendments

**1 — 28 Sep 2026, after the result: the build.** `delta-engine.js 2026-09-28a`: `changedTeamsThisSeason()`
compares his 2025 main team (most games; JAX = JAC, LA = LAR) with his team in his first 2026 game (current team if
none yet); a move multiplies the starting number by ×0.898 (`TEAM_CHANGE_MULT`), after the missed-time multiplier.
Verified old `27c` vs new: 66 movers flagged, identical to an independent list; each mover's starting number exactly
×0.898; every other player unchanged; DELTA Scores and graded calls unchanged; Engine Audit 32/32.

## Result (28 September 2026) — PASSED. Ship ×0.898.

Run once, `python3 scripts/teamchange-ship-study.py --run`, against this file as committed in `3ddb6b3`
(sha256 prefix `935565b9bdf0be5c`). Nothing above this section was changed after the run.

**Fitted on 2018–2022:** stayers ×0.983, movers ×0.829, so `r` = 0.843.

| Gate (265 held-out movers, 2023–2025) | Result |
|---|---|
| 1. Size ≥ 2% | **passed — 9.2%** (typical miss 3.554 → 3.228; average miss 2.769 → 2.500) |
| 2. Not a fluke | **passed — p = 0.0005** (0 of 2,000 shuffles as good) |
| 3. Every held-out season | **passed** — 2023 +15.0%, 2024 +2.4%, 2025 +10.2% |
| 4. No position worse than −1% | **passed** — QB +1.3%, RB +5.2%, WR +17.2%, TE +9.4% |

**Ship size by the §3 formula:** `r_all` = 0.834 over all eight seasons; the engine's existing ratio
0.929; **extra = 0.834 ÷ 0.929 = ×0.898.**
