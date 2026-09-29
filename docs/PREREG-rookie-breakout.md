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
