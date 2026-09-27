# PRE-REGISTRATION — Does DELTA Treat Team-Changers About Right?

**Written:** 27 September 2026. No outcome has been looked at: the only runs were `--count`
(eligibility, no outcomes), a crash test with every outcome replaced by random numbers (it proves the
code runs — nothing more), and a description of the live engine (no outcomes).
**Status:** locks on commit. Changes after the first run go in Amendments, with a reason.
**Script:** `scripts/teamchange-study.py` — `--count`, then `--run`, which refuses unless this file is
committed and unedited.

---

## 1. What This Is — And Is Not

**A calibration check, not a ship test.** The live engine's team adjustments (team system, QB quality,
play-caller) cannot be rebuilt for past seasons, so no replacement for them can be tested here. **This
study changes nothing in the engine.** If it finds the engine clearly off, that becomes a design question
for the owner.

**The question:** relative to the plain starting number, how much less (or more) do players who changed
teams in the offseason score than players who stayed — and does that match how much more cautious the
engine already is with them?

---

## 2. The Engine's Number, Recorded Before The Run

Live engine `2026-09-27c`, default format, 27 Sep 2026. For veterans whose 2025 team (most games) and
2026 team are known — **67 changed, 245 stayed** — the average of preseason projection ÷ starting
number is **×0.823 for changers and ×0.886 for stayers**. The engine's gap: **0.823 ÷ 0.886 − 1 = −7.1%.**

**This is total caution, from any source.** Changers tend to be older, so the age adjustment contributes
as well as the team adjustments. History's gap mixes the same things — older players decline whether
they move or not — so the comparison is like for like: *is the engine's total extra caution towards
changers about right?*

Team codes: the game logs use JAX and LA where the site uses JAC and LAR; mapped before counting.

---

## 3. The Measurement

- **Graded:** QB/RB/WR/TE with 8+ played games in the three prior seasons and 6+ in the season
  (the weights study's rules), 2018–2025, with both teams known.
- **Teams:** last season = the team he played most games for; this season = the team in his first game.
  nflverse uses today's franchise codes throughout, so relocations never count as changes.
- **Starting number:** the engine's rule (verified 315/315) × the missed-time multipliers shipped 27 Sep.
- **For each group,** the one multiplier on the starting number that best fits what players actually
  scored (`Σ start × actual ÷ Σ start²`). **Historical gap = changers' multiplier ÷ stayers' − 1.**
- **95% range:** 2,000 bootstrap resamples by player, seed 20260927.

---

## 4. The Verdict Bands, Fixed Now

| If… | Verdict |
|---|---|
| The engine's −7.1% sits inside the historical 95% range | **About right** |
| The whole range is below −7.1% (history harsher) | **Engine too soft on team-changers** |
| The whole range is above −7.1% (history gentler) | **Engine too harsh on team-changers** |

**Reported only:** the gap by position (30+ changers) and by season, and each group's multiplier.

**Stated in advance so it can be wrong:** "about right" — the engine's team adjustments were built with
this in mind, and 7% is a moderate figure.

---

## Pre-Lock Checks (27 September 2026)

| Check | Result |
|---|---|
| Known moves | Barkley 2024, Adams 2022, Allen 2024, Jacobs 2024, Henry 2024 → changed; Diggs 2023, Jefferson 2024, Kelce 2023 → stayed |
| Team codes over 2015–2025 | All 32 franchises use one code every season (no relocation artefacts) |
| `--run` refuses while this file is uncommitted | Refused |
| Full `--run` path, outcomes replaced by random numbers | Runs end to end — crash test only |

**Graded player-seasons** (printed by `--count`): 2,645 in total — **665 changed teams**, 1,980 stayed.
Changers by position: WR 276, TE 170, RB 152, QB 67.

---

## Amendments

*(none)*
