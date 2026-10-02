# PRE-REGISTRATION — Rookie Breakouts: Which Ones Hold Up?

**Written:** 29 September 2026. No outcome has been looked at: the only runs were `--count` and a listing
of breakouts, both from **rookie-year stats only**, and a crash test with every year-two outcome replaced
by random numbers (proves the code runs — nothing more).
**Status:** locks on commit. **Script:** `scripts/rookie-breakout-study.py`.

---

## 1. Why This Uses Different Evidence From Study 1

Study 1 (`docs/PREREG-rookie-sellhigh.md`) found selling breakout rookies was a coin flip, and its 57
breakouts' outcomes were then seen — including the remark that the biggest fades "looked heavy with
running backs and later picks". Testing those players or those traits again would be marking our own
homework. So this study uses:

- **Production, not price** — did he score as well in year two? (What moves the price anyway.)
- **Ten rookie classes, 2015–2024**, not five. Year-two production for these rookies has not been looked
  at in any study; the 2015–2019 classes have not been used for any rookie question.

---

## 2. The Test

- **Breakout:** a drafted rookie with 8+ games whose rookie-year points per game rank in the **top 12 QB,
  top 24 RB, top 24 WR or top 12 TE** among all players at his position with 8+ games that season —
  a starter-level rookie season. Half PPR + TE premium, the blend study's scoring.
- **Outcome:** year-two points per game ÷ rookie points per game (as a log). A year two with fewer than 4
  games is excluded and counted.
- **Traits — two primary, chosen for football reasons:**
  1. **Touchdown share** — the share of his rookie points that came from touchdowns. TDs swing year to
     year; predicted: **a higher share fades more.**
  2. **Volume** — targets + carries per game (QBs add pass attempts). Usage is sticky; predicted: **more
     volume holds up better.**
- **Traits — two secondary, flagged as weaker evidence** because Study 1's list suggested them after the
  fact: **running back** vs every other position (predicted to fade more); **rounds 1–2** vs later
  (predicted to hold up better).
- Touchdown share and volume are compared **within position** (each rookie against others at his
  position), so a running back's carries don't swamp a receiver's targets.
- **A trait is confirmed** when its effect lies in the predicted direction across its whole 95% range
  (2,000 bootstrap resamples, seed 20260929).

**Honest limit:** there are only **50 breakouts** (28 RB, 12 WR, 6 QB, 4 TE). Only a big effect can be
confirmed. "Not confirmed" means **not shown**, not "no effect". If the result is inconclusive, the next
step is adding older classes (the stats go back to 1999) — a new pre-registration, not a re-cut of this
one.

**Stated in advance so it can be wrong:** touchdown share confirmed (TD-driven breakouts fade); volume
likely but maybe too small a sample to confirm.

**Reported only:** the average year-two change for breakouts (the "sophomore slump"), the share that fell,
and the change by position.

---

## 3. What It Could Lead To

A confirmed trait becomes the basis for a **"Sell-High Watch"** on breakout rookies that have it — for
example, a TD-heavy breakout. That flag would itself need design and a forward check before it ships.
**This study changes nothing in the engine.**

---

## Pre-Lock Checks (29 September 2026)

| Check | Result |
|---|---|
| Games, scoring, IDs | Imported from `scripts/blend-study.py`; targets and carries from `scripts/usage-study.py` (58,855/58,855 joined); draft from `scripts/blend-study-rookies.py` |
| Breakout lists (rookie-year stats only) | 2017: Kamara, Hunt, Fournette, McCaffrey, Smith-Schuster, Engram · 2020: Herbert, Taylor, Jefferson, Gibson, Swift, Aiyuk, Edwards-Helaire |
| Counts | 50 breakouts: 2015 4 · 2016 4 · 2017 6 · 2018 3 · 2019 4 · 2020 7 · 2021 5 · 2022 2 · 2023 8 · 2024 7; rounds 1–2: 36 |
| `--run` refuses while this file is uncommitted | Refused |
| Full `--run` path, outcomes replaced by random numbers | Runs end to end — crash test only |

---

## Amendments

*(none)*

## Result (29 September 2026) — NO TRAIT CONFIRMED; both primary traits pointed the other way

**Record fix, 1 October 2026.** This section was written when the study ran (29 September 2026) and was handed
over for upload, but that upload never reached the repo — this file had only its lock commit. It is
copied here word for word from that session's record. Nothing was re-run, and nothing above this
section was changed.

**One correction to the copied text:** the sha256 prefix it gives (`3a6c9d79ea96d71a`) was not produced by the
run — the run printed no fingerprint — and matches no version of any pre-registration ever committed.
This file has had one version, committed in `b5e19df`: sha256 prefix **`09b0e5a565815405`**. Before running, the
run confirmed the committed file was byte-identical to the reviewed copy, so the outcome is unaffected.

Run once, `python3 scripts/rookie-breakout-study.py --run`, against this file as committed in `b5e19df`
(sha256 prefix `3a6c9d79ea96d71a`). Nothing above this section was changed after the run.

**Graded 49 of 50** (1 excluded, under 4 games in year two). **The sophomore slump is real but modest:**
breakouts' points per game fell **7.8%** on average in year two; **67%** fell. By position: QB −15%,
TE −15%, WR −12%, RB −3%.

| Trait (effect per step up in the trait, or group difference) | Predicted | Estimate | 95% Range | Confirmed |
|---|---|---|---|---|
| **Touchdown share** (primary) | fades | **+7.4%** | −0.2% to +15.7% | no — leans the **other way** |
| **Volume** (primary) | holds | **−8.0%** | −14.6% to −1.4% | no — clearly the **other way** |
| Running back (secondary) | fades | +11.8% | −3.6% to +28.8% | no |
| Rounds 1–2 (secondary) | holds | +4.7% | −15.3% to +31.5% | no |

**What it says:** none of the pre-registered traits tells you which breakout rookie to sell. The stated
expectation (touchdown share confirmed) was wrong. The volume result — high-volume breakouts fell *more* —
is the opposite of the prediction and cannot be acted on from this run: an effect found in the direction
nobody predicted, on 49 players, needs its own pre-registered test on fresh data (the 1999–2014 classes).
A plausible reading, untested: a rookie carrying an unusually heavy load is unlikely to carry it again.
**This study changes nothing in the engine.**
