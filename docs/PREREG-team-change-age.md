# PRE-REGISTRATION — Team Changes Through An Age Lens

**Written:** 27 September 2026. **Disclosure:** the overall team-change result on these same seasons has
been seen (`docs/PREREG-team-change.md`: changers −16.6% vs stayers). **The age breakdown has not.** The
only runs of this script were `--count` (group sizes, no outcomes) and a crash test with every outcome
replaced by random numbers (proves the code runs — nothing more).
**Status:** locks on commit. Changes after the first run go in Amendments, with a reason.
**Script:** `scripts/teamchange-age-study.py`, built on the locked `scripts/teamchange-study.py`
(imported unchanged: teams, eligibility, starting number, the multiplier fit).

---

## 1. The Owner's Hypothesis

A blanket team-change discount is wrong: Kenneth Walker (25, to KC), A.J. Brown (25, to PHI) and Jared
Goff (27, to DET) moved and improved; Stefon Diggs (30+, to HOU, NE, WAS) moved and declined. **The
claim: older players who change teams lose production; young ones can do as well or better.**

---

## 2. The Test

**Changers are compared with stayers of the same age**, because older players decline whether they move
or not. Within a group, **gap = changers' best-fit multiplier on the starting number ÷ stayers' − 1**
(the locked study's measure).

- **Age:** years on 7 September of the season (the engine's `AGE_AS_OF` rule), from nflverse birth dates.
- **Groups:** 26 and under · 27–28 · 29–30 · 31+ (24-and-under has only ~33 changers, so it is merged).
- **95% ranges:** 2,000 bootstrap resamples by player, seed 20260927.

**H1 — age matters:** the 29+ gap minus the 26-and-under gap has a 95% range entirely below zero.
**H2 — young changers are fine:** the 26-and-under gap's 95% range reaches zero or above.

| Result | Verdict |
|---|---|
| H1 and H2 | **Supported** — age drives it |
| H1 only | **Partly** — older changers clearly worse, but young ones lose some too |
| Not H1 | **Not supported** — the gap does not clearly grow with age |

**Reported only:** each age group's gap and range; the young vs 29+ gap by position.

**What it would mean:** if supported, the case is for an **age-linked** team-change adjustment rather
than a blanket one — itself a model change that would need its own pre-registered test. This study
changes nothing.

---

## Pre-Lock Checks (27 September 2026)

| Check | Result |
|---|---|
| Birth dates | Present for all 2,645 player-seasons |
| Examples | Diggs 2024 age 30.8 changed; A.J. Brown 2022 25.2 changed; Goff 2021 26.9 changed; Adams 2022 29.7 changed |
| `--run` refuses while this file is uncommitted | Refused |
| Full `--run` path, outcomes replaced by random numbers | Runs end to end — crash test only |

**Group sizes** (printed by `--count`): 26 and under — 205 changed, 1,275 stayed · 27–28 — 190, 350 ·
29–30 — 137, 195 · 31+ — 133, 160.

---

## Amendments

*(none)*
