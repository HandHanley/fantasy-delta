# PRE-REGISTRATION — New Value: Rookies Keep Draft Value Until 150 Offensive Snaps

**Written 13 November 2026, before any result.** The rule and its number are Steve's (13 Nov): "Let's do 150 snaps."

---

## Plain-English Summary (For Steve)

**The problem.** A rookie is valued on his draft slot until he plays, then on what he has done, however little. Jordyn
Tyson, the 8th pick, came off injured reserve in week 9, played 18 snaps, and fell from his draft value to 115th: a
"sell" off one game. Luther Burden, 16 snaps a game as a 2025 rookie, would have been judged the same way.

**The rule.** Until a first-year player has 150 offensive snaps this season, he keeps his draft-slot value, exactly as
if he hadn't played. From 150 on, he is valued normally. Offensive snaps only: a returner stays on draft value.

**What kind of change this is.** A rule about how much DELTA must see before it judges a rookie, like the no-team rule
and September's "no call yet" for rookies. It is **not** claimed to make predictions better. The check below only makes
sure it doesn't make them worse.

## 1. The Rule

- **Who:** first-year players (`rookie_Y`) in the value's season.
- **Snaps:** offensive snaps in regular-season weeks up to the value's week, from nflverse snap counts, joined to GSIS
  ids through nflverse `players.csv` (`study/rookie_snaps.py`, the one source for the check and the build).
- **Under 150:** his value is his incoming-rookie value (the draft-slot value, kind R0, the same one he had before his
  first game).
- **150 or more:** unchanged (today's in-season value).
- **Everyone else:** unchanged.
- **The number is fixed.** No other threshold is run, reported or chosen.

## 2. The Check (Decides Whether It Ships)

- **Rows:** week 9, test seasons 2013–2022: the rows of `PREREG-ovs-small-samples.md`, built by `ovs_small_samples.py`'s
  frame, which must reproduce today's value (RMSE 48.4611) first. Snap counts start in 2013 (the 2012 file is empty;
  found when the script's coverage check stopped it, before any result), so every test season has them. Nothing is fitted, so the fit seasons are not used.
- **Today, as the live build values rookies:** a first-year QB with no real game, or any other first-year player with no
  available game, takes his incoming-rookie value; everyone else takes the in-season value.
- **Decides:** on the first-year rows, the typical miss (RMSE, three seasons ahead, FV3) under the rule must be **no more
  than 0.5% worse** than today.
- **Passes →** the rule goes into the weekly build. **Fails →** back to Steve; not shipped.

## 3. Reported, Deciding Nothing

- Typical miss on all rows, and on first-year rows by position.
- Paired permutation test on first-year rows (a player's rows shuffled together, 10,000 shuffles).
- What first-year rows produced as a share of their value: under the threshold and over it, today and under the rule.
- How many first-year rows fall under the threshold.
- **2026 page:** every first-year player, today vs. under the rule, with snaps.

## 4. Prior Looks

- **12 Nov (`PREREG-ovs-small-samples.md`):** a smooth blend toward the incoming-rookie value, by games (K = 1), was
  1.8% better on first-year rows (RMSE 56.74 → 55.70) and 0.7% better overall, under the 2% bar. That is why the rule is
  expected not to hurt, and why it is framed as a rule, not an accuracy claim.
- **This rule, with snaps, has not been compared with any outcome.**

## 5. Not Licensed Here

- The DELTA Score, the live site's DELTA Value, buy/sell calls on the live site.
- Any other threshold, or a snaps rule for veterans.
