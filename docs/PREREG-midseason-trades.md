# PRE-REGISTRATION — Mid-Season Team Changes

**Written:** 30 September 2026. **Status:** DRAFT — locks when committed together with the script, byte-identical
to the copy reviewed. **Script:** `scripts/midseason-trade-study.py` (imports the locked `scripts/blend-study.py`
loader, scoring, starting number and Start Profile penalty unchanged).

---

## 1. The Question

When a player changes teams **during** a season, does he score less over the rest of that season than DELTA's
in-season forecast says — compared with players who stayed put all season?

The offseason version is settled: offseason movers score about 17% below their own history relative to stayers,
and the engine ships ×0.898 for them (`docs/PREREG-team-change-ship.md`, passed 28 Sep). That rule deliberately
does not catch a player traded mid-season, because nothing had tested it. The 2026 trade deadline is 10 November.

---

## 2. What The Engine Does Today (Measured 30 Sep, Live `29a`)

A fake trade was run through the real engine on a scratch copy of today's data. The roster feed updates a
player's team nightly, so his **preseason part** picks up the new team's adjustments (quarterback, system).
The **in-season part** — this season's games — stays as played for the old team, by design. The ×0.898 never
fires, before or after games with the new team.

| Fake Trade | Projection Before | Trade Night | Change |
|---|---|---|---|
| Garrett Wilson, NYJ → KC | 10.90 | 11.24 | +3.1% |
| Garrett Wilson, NYJ → CLE | 10.90 | 11.00 | +0.9% |
| Courtland Sutton, DEN → NYG | 7.66 | 7.45 | −2.7% |
| Jakobi Meyers, JAC → BUF | 9.27 | 9.05 | −2.4% |

So today a mid-season move nudges a projection a few percent either way, depending on the destination.

---

## 3. The Data

nflverse weekly player stats and snap counts, regular season, downloaded from nflverse-data GitHub releases.

- **Graded seasons: 2016–2025.** Snap counts for 2012 exist as a file with **zero rows**, so the played-game
  rule cannot be applied to 2012. Starting at 2016 means every graded season and all three of its prior seasons
  (2013 onward) use the same rule. Decided before any outcome was seen.
- **Played game:** the live DNP rule (1+ offensive snap or any recorded production), as in the blend study.
- **Teams:** from each week's stats row. nflverse uses today's franchise codes, so relocations are never moves.

**Mover** — a veteran (8+ played games across the three prior seasons) whose team changed **exactly once**
during the season, with **3+ played games before the switch and 3+ after**. The forecast is made at the
checkpoint just before his first game for the new team.

**Stayer** — same history rule, one team all season, graded at every checkpoint from Week 3 to Week 16 with
3+ games on each side.

**Excluded from both groups:** anyone whose first team this season differs from his main team last season
(an offseason mover — the engine already gives him ×0.898, and this test must not blur the two), and anyone
who switched more than once.

**Counts** (printed by `--count`; no outcomes): **51 movers** (WR 32, RB 11, TE 8, **QB 0**); 25,774 stayer
checkpoints from 2,506 stayer seasons. By season: 2016 1 · 2017 6 · 2018 6 · 2019 8 · 2020 1 · 2021 5 ·
2022 12 · 2023 3 · 2024 6 · 2025 3. Halves: 22 (2016–20) and 29 (2021–25). Most switches fall after Weeks
6–10. The exclusions cost 37 players who had already moved in the offseason, 7 multi-switchers, 5 with thin
history and 3 short of the played-game minimum.

---

## 4. The Forecast

The engine's shipped in-season form D at K = 4 (every graded player has 8+ prior games):
`(w × PPG so far + (1 − w) × starting number) × (1 + 0.5 × Start Profile penalty)`, `w = G ÷ (G + 4)`.
Starting number and penalty exactly as the blend study built them. Outcome: points per game over every played
game **after** the switch, half PPR with TE premium (backtest.js scoring).

---

## 5. The Test — Built So It Cannot Pass By Accident

Every forecast runs a little high, so "shrink movers" would beat "don't" even if moving meant nothing. So
**both sides are calibrated on stayers first**:

- **Baseline:** a mover forecast like a stayer — the forecast × the stayers' best-fit multiplier **at the same
  checkpoint week**.
- **Candidate:** the baseline × **0.898** — the size already shipped for offseason moves. **Nothing about the
  size is fitted on these 51 players.** The only thing the candidate knows that the baseline doesn't is that he
  changed teams.

**Overlap with the 0.898, disclosed:** the offseason study defined a stayer by his first game, so most of these
51 sat among its ~1,200+ **stayers**, whose full seasons set the stayer side of the 0.898. A few percent of that
group. If mid-season movers really do fall off, their presence nudged the 0.898 slightly closer to 1 — a
slightly **smaller** cut, never a larger one. None of them was an offseason mover.

**Out of sample by season:** each season's movers are forecast with stayer multipliers fitted on the **other**
nine seasons (leave one season out).

**Pass mark — all four:**
1. **Size:** typical miss (RMSE) at least **2% lower** than the baseline, pooled over all 51.
2. **Not a fluke:** paired shuffle test — each player's two real forecasts swapped at random, 2,000 shuffles,
   seed 20261001, one-sided, **p < 0.05**.
3. **Both halves:** better in 2016–2020 **and** in 2021–2025.
4. **No position harmed:** no position with 25+ movers more than 1% worse (in practice: WR).

**Reported only, never gated:** a size fitted freshly from the movers (leave one season out, and over all ten
seasons); average miss (MAE); each position.

---

## 6. The Honest Odds — Measured Before Locking

The crash test replaced every outcome with synthetic numbers **before anything was computed** (real outcomes
are discarded in memory in `--count` and `--crash`), with noise set to reproduce the blend study's real typical
miss scaled to these movers (0.35), and a pessimistic level (0.45). 200 simulations each.

| What The Synthetic Movers Really Do | How Often The Test Passes (Realistic / Pessimistic Noise) |
|---|---|
| Nothing — score exactly like stayers | **3% / 1%** — it cannot be fooled by noise |
| 10% below stayers | **20% / 23%** |
| 15% below stayers (about the offseason size) | **54% / 38%** |

**Read plainly:** the design is honest, but 51 players is a small sample. If mid-season movers fall off as much
as offseason movers do, this test has **roughly a coin-flip chance** of confirming it. A fail would mean "not
shown with the evidence available", **not** "mid-season moves don't matter". Fitting a fresh size instead of
testing 0.898 was also crash-tested and is weaker (18% at the 15% level), which is why the shipped size is the
test.

---

## 7. What Ships If It Passes

**Size:** ×0.898 — the number tested. No new constant.

**The engine's rule:**
- **Who:** a veteran with 8+ played games across the three prior seasons whose team in his **first played
  game this season** differs from his **current team** or the team in his **most recent played game**, and
  whom the offseason rule did not already catch. Not QBs (none in the sample), rookies or thin-history players —
  untested, so the rule does not fire for them.
- **What:** ×0.898 on the parts of the in-season projection built on old-team information — the preseason part
  and the games played for his old team. **Games for his new team count at face value.** At the switch, with no
  new-team games yet, this is exactly the tested forecast × 0.898. As new-team games accumulate the cut fades
  on its own; that fade is **untested** and flagged, following the blend's existing principle that games
  already played in a system need no further team adjustment.
- **Unchanged:** the directional team adjustments (a move into a strong situation still helps), the DELTA
  Score, and the offseason rule. Before-and-after table; Engine Audit 32/32.

**If it fails:** nothing changes. Mid-season movers keep today's treatment. **Do not re-run with different gates,
a different checkpoint or a different minimum** hoping for a pass.

---

## 8. Every Earlier Look At This Data

- **30 Sep (this session):** a raw count of mid-season movers, 2012–2025, from team, week and position columns
  only (121 with 3+ stat weeks each side). `--count` and an attrition breakdown (teams and game counts only).
  Crash tests on synthetic outcomes. In `--count` and `--crash` the script builds real outcomes in memory and
  discards them before anything is computed or printed — the same as earlier studies' count modes.
- **26 Sep, blend study:** graded every player at Weeks 3/6/9/12 on 2018–2025, which pooled in some of these
  movers without ever splitting them out. Their mover-versus-stayer difference has never been computed.
- **27–28 Sep, offseason team-change studies:** their movers were offseason movers — a different set. But their
  **stayers** included most of these 51 (a stayer was defined by his first game), so these players' full seasons
  are inside the 0.898's stayer side. Their mid-season split was never computed. See §5.

---

## Pre-Lock Checks (30 September 2026)

| Check | Result |
|---|---|
| Loader, scoring, starting number, penalty | Imported unchanged from the locked `scripts/blend-study.py` |
| Engine today, fake trades through live `29a` | §2 — team adjustments only; ×0.898 never fires |
| 2012 snap counts | 0 rows — study starts 2016 (§3) |
| `--run` refuses while this file is uncommitted | Refused |
| Full path on synthetic outcomes | Runs end to end; pass rates in §6 |

---

## Amendments

*(none)*

## Result

*(not run)*
