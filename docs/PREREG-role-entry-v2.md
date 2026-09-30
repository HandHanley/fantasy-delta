# PRE-REGISTRATION — Role-Entry Odds v2: A Capped Curve, Tested On Unseen Classes

**Written:** 29 September 2026. No outcome has been looked at: the only runs were `--count`, self-checks of
the capped fit on made-up data, and a crash test with every outcome replaced by random hits.
**Status:** locks on commit. **Script:** `scripts/role-entry-v2-study.py`.

---

## 1. Why

The first odds curve (`docs/PREREG-role-entry.md`) beat position averages by 25% but failed the honesty
check: **too confident at the top** — players it rated about 77% hit 65%, and it gave a top-5 RB "100%".
The fix must be tested on players it has never seen, because the first test's miss has now been looked at.

## 2. The Owner's Point About Eras — And How The Design Answers It

The owner (29 Sep): 2000–2014 was a different game, so its numbers need not apply to today's rookies.
**Agreed.** So the older classes are used only to test the **method**:

- **Primary test — the method, on unseen classes:** the capped curve, fitted and checked **within
  2000–2014** (each class predicted from the other fourteen of its own era). No 2000–2014 number is ever
  shown for today's rookies.
- **What ships, if it passes:** odds fitted on **2015–2023** — today's game — with the validated method.
- **Required as well:** the capped curve must also pass the honesty check on 2015–2023. (Not independent
  evidence — that data showed the first curve's failure — but the shipped odds must not be dishonest on
  the modern classes.)
- **The owner's "confirmation", reported only:** both eras' curves side by side, and the old-era curve
  applied to the modern classes. If they agree, it's confirmation; if not, it measures how much the game
  changed — and the modern odds are the ones used either way.

---

## 3. The Method

- **Capped curve:** per position, `P(hit) = c × logistic(a + b × ln(pick))`, with **one pooled ceiling
  `c` below 100%** — no draft slot guarantees a fantasy starter. The rest is the first study's: hit = a
  starter-level season in the first three (top 12 QB / 24 RB / 24 WR / 12 TE by points per game, 8+ games).
- **Old-era data:** 1,207 drafted QB/RB/WR/TE, 2000–2014; stats from nflverse weekly files 2000–2016 (a
  game counts when a stat was recorded — no snap counts before 2012). **99 drafted players have no nflverse
  ID and count as misses:** an ID is issued once a player records stats, and those missing are never-played
  picks (Giovanni Carmazzi, Maurice Clarett, Eric Crouch, Kenny Irons). Dropping them would inflate the
  late-round odds. ID coverage: round 1 100%, round 7 80%.
- **Honesty check:** as the first study — ten-bin calibration error no worse than the 95th percentile of a
  perfectly honest model's, simulated 2,000 times.

## 4. The Pass Mark

**Ship the odds display only if both:** (1) **honest on 2000–2014** (primary); (2) **honest on 2015–2023**.

**Reported only:** the first (uncapped) curve on 2000–2014; hit rates by era; both eras' odds at picks 5,
20, 45, 80, 120, 180, 240 and their ceilings; the old-era fit applied to 2015–2023.

**Stated in advance so it can be wrong:** passes on 2000–2014; passes on 2015–2023; the eras broadly agree
on the curve's shape, with running backs hitting more often in 2000–2014.

---

## 5. What It Could Lead To

If both pass: a design for **rookie odds on player cards**, fitted on 2015–2023 — e.g. *"Chance of a starter
season by year 3: 13%"*. Display only: no projection, Score or call changes. Build agreed with the owner.

---

## Pre-Lock Checks (29 September 2026)

| Check | Result |
|---|---|
| Capped fit, made-up data, n = 6,000 | Slope recovered exactly (−1.0); predicted odds within 1 point of the truth in every pick range below the top five (top five 0.66 vs 0.62) |
| Ceiling at real-world size (n = 1,200) | The ceiling itself is loosely pinned (0.70 → 0.78–0.80: it trades off against the curve's height) — but the **odds** track the data; over 8 random samples the predictions average **0.8 points** from the truth |
| Old-era coverage | 1,207 drafted; 1,108 with an nflverse ID (92%); 99 counted as misses |
| Crash test, random hits | Runs end to end |
| `--run` refuses while this file is uncommitted | Refused |

---

## Amendments

*(none)*

## Result (30 September 2026) — Method HONEST on unseen classes · Modern odds NOT honest · Nothing ships

Run once, `python3 scripts/role-entry-v2-study.py --run`, against this file as committed in `5e5de54` /
`c80b49e`. Nothing above this section was changed after the run.

| Test | Calibration Error | Honest-Model Limit | Result |
|---|---|---|---|
| **Primary — capped method, unseen 2000–2014** (1,207 players) | **1.9 points** | 3.0 | **HONEST** |
| **Required — capped method, 2015–2023** (712 players) | **5.2 points** | 4.2 | **NOT HONEST** |
| Reported — first (uncapped) curve, 2000–2014 | 2.9 | 3.1 | honest |
| Reported — 2000–2014 fit applied to 2015–2023 | 3.9 | 4.0 | honest (barely) |

**§4 requires both → the odds display does not ship.** The modern miss has the first study's shape: the
top bin predicted 75.6%, actual 62.5%; the middle bins predicted 11–16%, actual 17–24%. The fitted
**ceilings differ sharply by era — 0.68 (2000–2014) vs 0.96 (2015–2023)** — so on the modern data the cap
barely binds, and it cannot rein in a top end that 712 players do not pin down.

**The owner's era question (reported):** hit rates 2000–2014 vs 2015–2023 — QB 13% vs 21%, **RB 22% vs 29%**,
TE 17% vs 14%, WR 14% vs 16%. Odds at pick 5: RB 68% vs 96%, TE 68% vs 95%, WR 65% vs 82%, QB 51% vs 53%.
**The eras differ most at the top of the draft** — today's top running backs and tight ends hit far more
often. From pick ~45 down, the eras are close. The stated expectations: old-era pass — right; modern pass
— **wrong**; "running backs hit more often back then" — **wrong** (the reverse).

**What it says:** the capped method gives honest odds where there is enough data (1,207 players), but the
modern classes alone are too few to pin the top of the draft honestly — and the eras differ exactly
there, so the old era cannot stand in. **This study changes nothing in the engine.**
