# PRE-REGISTRATION — Do High-Volume Breakout Rookies Fade More? (Fresh Classes)

**Written:** 29 September 2026. No outcome has been looked at: the only runs were `--count` and a listing
of breakouts (rookie-year stats only) and a crash test with every year-two outcome replaced by random
numbers (proves the code runs — nothing more).
**Status:** locks on commit. **Script:** `scripts/rookie-volume-study.py`.

---

## 1. Where This Comes From

Study 2 (`docs/PREREG-rookie-breakout.md`, classes 2015–2024) predicted that high-volume breakout
rookies would hold up better. The opposite happened: **heavier volume went with a bigger year-two
fall** (−8% per step up in volume, range −14.6% to −1.4%). A pattern found against the prediction, on
49 players, is a lead, not a finding. The fair check is **the same test, in that direction, on data no
DELTA study has touched.**

**Plausible reason, untested:** a rookie carrying an unusually heavy load is unlikely to carry it again —
a hot start in usage regresses like a hot start in points.

---

## 2. The Test

- **Classes: 1999–2002 and 2009–2014.** 2003–2008 are left out because nflverse has **no target data**
  for those seasons, so a receiver's volume cannot be measured.
- **Breakout, volume and outcome exactly as Study 2:** a drafted rookie with 8+ games in the top 12 QB /
  24 RB / 24 WR / 12 TE by points per game; volume = targets + carries per game (QBs add pass attempts),
  compared within position; outcome = year-two points per game ÷ rookie points per game (log), year two
  with 4+ games. Scoring: the blend study's half PPR + TE premium function.
- **Two disclosed differences:** snap counts only exist from 2012, so a game counts when the player
  recorded a stat (for starter-level breakouts this rarely matters); players link to draft classes by
  nflverse ID where the draft file carries one (about 9 in 10 in these years).

**The one question:** is the effect of volume on the year-two change **negative across its whole 95%
range** (2,000 bootstrap resamples, seed 20260929)?

| Result | Verdict |
|---|---|
| Whole range below zero | **Confirmed** — high-volume breakout rookies fade more |
| Range reaches zero or above | **Not confirmed** on fresh classes |

**Honest limit:** **39 breakouts** (20 RB, 10 WR, 5 TE, 4 QB) — even fewer than Study 2. Only an effect
at least as strong as Study 2's is likely to be confirmed. "Not confirmed" means **not shown**.

**Reported only:** touchdown share (Study 2 leaned "TD-heavy holds better"), the average year-two change,
the share that fell, and the change by position.

**Stated in advance so it can be wrong:** not confirmed — 39 players is a thin test, even if the effect is
real.

---

## 3. What It Could Lead To

Confirmed here **and** in Study 2 would make "a high-volume breakout rookie is a sell-high candidate" the
first rookie signal with independent support — the basis for a **"Sell-High Watch"** design, which would
still need a forward check before it ships. **This study changes nothing in the engine.**

---

## Pre-Lock Checks (29 September 2026)

| Check | Result |
|---|---|
| Target data by season (receivers with targets recorded) | 1999–2002 84–87% · **2003–2008 0%** · 2009–2014 86–88% |
| Breakout lists (rookie-year stats only) | 2000: Mike Anderson, Jamal Lewis · 2012: Robert Griffin III, Doug Martin, Andrew Luck, Russell Wilson, Alfred Morris, Trent Richardson |
| Counts | 39 breakouts: 1999 4 · 2000 2 · 2001 2 · 2002 3 · 2009 1 · 2010 4 · 2011 4 · 2012 6 · 2013 6 · 2014 7 |
| `--run` refuses while this file is uncommitted | Refused |
| Full `--run` path, outcomes replaced by random numbers | Runs end to end — crash test only |

---

## Amendments

*(none)*
