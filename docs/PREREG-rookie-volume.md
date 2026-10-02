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

## Result (29 September 2026) — NOT CONFIRMED

**Record fix, 1 October 2026.** This section was written when the study ran (29 September 2026) and was handed
over for upload, but that upload never reached the repo — this file had only its lock commit. It is
copied here word for word from that session's record. Nothing was re-run, and nothing above this
section was changed.

**One correction to the copied text:** the sha256 prefix it gives (`dd62e4b45f4ae394`) was not produced by the
run — the run printed no fingerprint — and matches no version of any pre-registration ever committed.
This file has had one version, committed in `80da01f`: sha256 prefix **`3dd75fc490324b43`**. Before running, the
run confirmed the committed file was byte-identical to the reviewed copy, so the outcome is unaffected.

Run once, `python3 scripts/rookie-volume-study.py --run`, against this file as committed in `80da01f`
(sha256 prefix `dd62e4b45f4ae394`). Nothing above this section was changed after the run.

**Graded 36 of 39** (3 excluded, under 4 games in year two).

| | Study 2 (2015–2024) | This Study (1999–2002, 2009–2014) |
|---|---|---|
| **Volume**, per step up | −8.0% (−14.6% to −1.4%) | **−4.2% (−16.0% to +9.1%)** |
| Touchdown share, per step up (reported) | +7.4% (−0.2% to +15.7%) | **−9.0% (−19.9% to +5.6%)** |
| Average year-two change | −7.8% | −8.6% |
| Share that fell | 67% | 50% |

**Verdict (§2): not confirmed.** Volume leans the same way as in Study 2 but half as strongly, and the
range reaches zero. Touchdown share flipped sign between the two samples — a sign that neither result
was more than noise. The stated expectation (not confirmed) was right.

**Across Studies 1, 2 and this one:** breakout rookies' scoring slips about **8% in year two** — consistent
in all three samples — but no trait tested (touchdown share, volume, position, draft capital) reliably
picks out which ones fade, and selling breakouts at the end of the rookie year was a coin flip on price.
**This study changes nothing in the engine.**
