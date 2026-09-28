# PRE-REGISTRATION — Team Changes Among Players Who Matter In Fantasy

**Written:** 27 September 2026. **Disclosure — third look at the same seasons.** Already seen: the
overall team-change gap (−16.6%, `docs/PREREG-team-change.md`) and the age breakdown (young changers
−18.3%, 31+ −16.7%, `docs/PREREG-team-change-age.md`). **Not seen: anything restricted to fantasy-
relevant players.** Every extra slice of the same data raises the odds of a pattern appearing by
chance, so this result is **evidence for a design question, never a licence to ship**: any model change
it suggests needs its own pre-registered test.
The only runs of this script were `--count` (no outcomes) and a crash test with every outcome replaced by
random numbers (proves the code runs — nothing more).
**Status:** locks on commit. **Script:** `scripts/teamchange-top150-study.py`, built on the two locked
team-change scripts, imported unchanged.

---

## 1. The Owner's Hypothesis

The young-mover drop is driven by fringe players and busts — a player gets a chance, fades, moves, and
never earns a role again (Jahan Dotson: strong rookie year in Washington, faded, traded to Philadelphia
with little role, then Atlanta). Modifiers should be about players who matter in fantasy lineups.
**Claim: among fantasy-relevant players, moving young does not cost production.**

---

## 2. The Test

- **"Top 150" = each season's 150 highest preseason starting numbers**, all positions together — decided
  with preseason information only, never by how the season turned out. (Dotson: 103rd going into 2023,
  148th into 2024 when he moved — inside; 207th into 2025 — outside.)
- Changers vs stayers **of the same age**, as the age study: gap = changers' best-fit multiplier on the
  starting number ÷ stayers' − 1; 95% ranges from 2,000 bootstrap resamples by player, seed 20260927.

**Q1 — does DELTA treat top-150 team-changers about right?** Recorded before the run from the live
engine (27 Sep): among the top 150 veterans by starting number, the engine's preseason projection ÷
starting number averages **×0.843 for 27 changers and ×0.928 for 123 stayers — a gap of −9.2%.**

| If the top-150 historical 95% range… | Verdict |
|---|---|
| includes −9.2% | **About right** for players who matter |
| lies entirely below −9.2% | **Engine too soft** on top-150 changers |
| lies entirely above −9.2% | **Engine too harsh** on top-150 changers |

**Q2 — the owner's hypothesis:** among top-150 players, the 26-and-under changers' gap has a 95% range
that reaches zero or above → **supported** (busts drove the overall young-mover drop). Otherwise **not
supported**.

**Reported only:** every age group and position within the top 150.

**Stated in advance so it can be wrong:** Q2 supported — the owner's reading of who moves young is
plausible — and Q1 closer to the engine than the all-player result was.

---

## Pre-Lock Checks (27 September 2026)

| Check | Result |
|---|---|
| Ranking uses preseason information only | Starting number (engine rule × shipped missed-time sizes), per season |
| Example | Dotson 2023 rank 103 stayed; 2024 rank 148 changed; 2025 rank 207 (outside) |
| `--run` refuses while this file is uncommitted | Refused |
| Full `--run` path, outcomes replaced by random numbers | Runs end to end — crash test only |

**Group sizes** (printed by `--count`): 1,200 top-150 player-seasons — **262 changed**, 938 stayed.
26 and under: 74 changed / 531 stayed · 27–28: 60 / 177 · 29–30: 48 / 114 · 31+: 80 / 116.

---

## Amendments

*(none)*
