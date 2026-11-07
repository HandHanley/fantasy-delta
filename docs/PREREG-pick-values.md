# PRE-REGISTRATION — Rookie Picks On DELTA's Own Value Scale

**Drafted:** 7 November 2026, before any result exists. **Status: LOCKED 7 Nov 2026.**
Locked by committing this document with `study/pick_values.py` before the confirmatory run. Lock commit: the commit
titled "Lock pre-registration: rookie picks on the own value scale". Changes after that are amendments (§11).

---

## Plain-English Summary (For Steve)

**The idea.** A rookie pick is worth what the players taken there usually turn into. So a pick's value is the average
five-season value (the same points-above-a-starter measure as the Own Value Scale) of the real players taken in that
part of past rookie drafts: Early 1st (1.01–1.04), Mid 1st, Late 1st, 2nd round, 3rd round.

**The test that matters for a trade calculator: are picks priced fairly against players?** If a Mid 1st and a veteran
both read 3,000 on the ruler, the Mid 1st's players should go on to produce about as much as veterans valued at 3,000
did. If picks consistently produce more or less, the calculator would be tilted for or against picks, and we'd correct
it by one measured multiplier.

Because a pick's value *is* its tier's real average, the picks side is honest by construction. What's really being
tested is the other side: do veterans the ruler calls 3,000 actually go on to produce like 3,000? If they produce
more, picks are overpriced next to them; if less, underpriced.

**What you get back.** Each pick tier on the 0–10,000 ruler, whether picks are fairly priced against players (and the
fix if not), and how much riskier a pick is than a player of the same value.

---

## 1. What This Tests, And What It Doesn't

**Tests:** whether rookie-pick values built as tier averages sit fairly on the Own Value Scale (OVS,
`docs/PREREG-own-value-scale.md`, passed 7 Nov), measured against veterans with the same value.

**Does not test, and does not license changing:** the DELTA Score, projections, model value, buy and sell calls, the
site's current pick values, or how incoming rookies are valued once they're drafted (§10). No market data is read.
Nothing on the site changes.

## 2. Prior Looks At The Data — Full Disclosure

- **4 Oct, `docs/PREREG-future-first.md`.** Same rookie-draft order and the same 351 slots. Starter seasons in years 1–3:
  Early 1st 1.60, Late 1st 0.75; the 1.01 stood apart (10 of 10 hit). So the tiers' order is already known; their
  value against veterans is not.
- **7 Nov, `docs/PREREG-own-value-scale.md`.** OVS results for veterans and incoming rookies on these same seasons. For
  incoming rookies, draft-slot bands beat OVS (84.3 vs 87.4 typical miss).
- **7 Nov, this draft.** The slots were rebuilt with the Future Firsts code (351, matching it). No pick's outcome was
  compared with any veteran's before the crash tests.

## 3. Data

- **Rookie-draft order:** Fantasy Football Calculator dynasty rookie ADP, 12-team, classes 2014–2023
  (`data/fixtures/ffc-rookie-adp-YYYY.json`), built into slots by `scripts/future-first-study.py`'s own code, unchanged
  (name matching, exceptions and drops as written there). Mock drafts, **1QB** order, late summer. FFC allows commercial
  use with credit.
- **Used here: classes 2014–2021** (279 slots). These are the classes whose five-season window has closed (2021 class:
  2021–2025). 2022–2023 can't be scored on five seasons.
- **Veterans and outcomes:** exactly the OVS study's snapshots, FV5 and OVS values (12-team superflex lines, half PPR +
  TE premium). A pick's outcome is the FV5 of the player taken there, over his first five seasons (his class year
  onward), on his draft position's line. For a drafted player this equals his incoming-rookie snapshot's FV5 (asserted);
  for an undrafted one it is computed the same way from the stats.

## 4. Pick Values

- **Tiers (fixed):** Early 1st (slots 1–4), Mid 1st (5–8), Late 1st (9–12), 2nd (13–24), 3rd (25–36).
- **A tier's value for class `c`** = the average FV5 of the players in that tier in the **other seven classes**
  (leave one class out). Later classes help value earlier ones, so this is a fairness check, not a replay of what was
  knowable at the time (there are too few classes for that). Every comparison below gets the same advantage.
- **Fixed conventions, not tested here:** a pick a year further out is worth 0.9 of the same pick this year (FV5's own
  yearly discount). A first whose slot isn't known yet is the average of the three first-round tiers.

## 5. The Question: Are Picks Fairly Priced Against Veterans?

For each pick (class `c`, value `v` from §4):
- **Its matched veterans:** the OVS test veterans of the same offseason (`t = c − 1`) whose OVS value is within ±10% of
  `v`. Fewer than 10: widen to ±20%. Still fewer than 10: the pick is dropped and counted.
- **Matched outcome `m`:** the average FV5 those veterans actually produced (same five seasons as the pick).

**The measure:** `R = (total FV5 the picks produced) ÷ (total of their matched veterans' averages)`. R = 1 means picks
produced exactly what equally valued veterans did.

**The rule (decided now):** a 95% range for R from 4,000 resamples (picks resampled within each class, veterans
resampled by player, tier values and matches rebuilt in every resample, lesson 14). Seed 20261107.
- **Range includes 1.0:** picks go on the ruler at their tier values, unchanged.
- **Range excludes 1.0:** every pick value is multiplied by R. That is reported as the fix, and as a finding.

## 6. Reported, Deciding Nothing

- Each tier's value on the 0–10,000 ruler (all eight classes; the ruler's 10,000 is the top 2025 OVS value), its
  number of picks, and its range.
- **The 1.01 on its own** (8 picks), against the Early 1st tier.
- **Riskiness:** in one-for-one pairs of a pick against one of its matched veterans, how often the pick produced more.
  Picks are lottery tickets, so this can sit below 50% even when R = 1.
- R by tier, by pick position (QB vs the rest; the order is 1QB but the scoring is superflex), and by class halves
  (2014–2017, 2018–2021).

## 7. Crash Tests, Before Lock

**What a tilt looks like (pre-lock A1).** A pick's value is its own tier's average, so picks always produce about what
their value says. A tilt between picks and players can only come from the veterans: if veterans valued at 3,000
reliably produce 3,600, a 3,000 pick is a worse deal than a 3,000 player. So the synthetic worlds plant the tilt in
the veterans. (The draft planted it in the picks, which can't work: the picks' values would move with it.)

Run with the real estimator, real slots and real veteran OVS values; 1,000 resamples per run (4,000 confirmatory):
- **Veterans:** `y = OVS × η ÷ R_true`, where `η` is the real veterans' outcome-to-OVS ratios, shuffled among veterans
  of the same position and OVS tenth, scaled to average exactly 1 in each group (so the fair world's veterans are
  calibrated). Veterans with OVS 0 score 0.
- **Picks:** `y = L_tier × ε`, where `L` is the tier averages and `ε` the picks' outcome-to-tier-average ratios,
  shuffled across all picks, scaled to average exactly 1.

1. **Fair world (R_true = 1):** the range must include 1.0 in **at least 90% of 200 runs**.
2. **Tilted world (R_true = 0.7, picks worth 70% of equal veterans):** the range must exclude 1.0 in **at least 80% of
   200 runs**. If not, the study is too small to see a 30% tilt, and Steve hears that before any real result.
   R_true = 1.3 is reported (50 runs).
3. **Leak checks (asserted):** scrambling veteran outcomes leaves every match unchanged (matching reads OVS only);
   changing one class's pick outcomes leaves that class's own pick values unchanged.

Real outcomes enter the crash tests only as the shapes of their spreads and the tier averages. No pick's outcome is
compared with a veteran's before the lock.

**A first try, disclosed (pre-lock A2).** Drawing `η` from all of a position's veterans at once (any value) gave a
fair-world range about 2.0 wide with a typical R of 1.49: a veteran valued near zero who then broke out has a huge
ratio, and swapping that onto a 3,000 veteran is not a world that exists. Swapping only within the same tenth of
value fixed it (20 runs: range about 0.44 wide, typical R 1.03). That trial used 4 and 20 runs; no real comparison.

## 8. Limits, Stated Now

- **Mock drafts, 1QB order, late summer.** In superflex rookie drafts quarterbacks go earlier, so 1QB tiers may hold
  QBs who'd have gone higher; R by position is reported for that reason.
- **Eight classes** (279 picks). Tier values carry real uncertainty; the ranges are reported.
- **Five seasons only.** A pick's value after year five isn't counted, the same as for players on the ruler.

## 9. What Each Result Allows (Each Still Needs Steve's OK)

| Result | What It Allows |
|---|---|
| Fair (range includes 1.0) | Pick tiers go on the ruler at their measured values; with OVS, the Trade Calc could run without FantasyCalc |
| Tilted (range excludes 1.0) | Same, with every pick multiplied by the measured R |
| Crash test 2 fails | Reported before any real result; Steve decides whether to run |

## 10. Not Licensed Here

- **Incoming rookies after the NFL draft** (a pick that has become a named player): whether OVS or draft-slot bands
  should price them is its own question, needing fresh classes.
- **Superflex rookie-draft order**, other league sizes, and in-season updates.

## 11. Amendments

**Before lock**
- **A1 (7 Nov).** Crash-test tilt planted in the veterans, not the picks (§7). Plain English in §7.
- **A2 (7 Nov).** Veteran noise swapped only within position and OVS tenth (§7), after a first try was unrealistic.
- **A3 (7 Nov).** Of the 279 picks, 276 have an incoming-rookie snapshot (outcome read from it, and checked against a
  fresh computation where the positions agree); 3 were undrafted in the NFL and are scored from the stats directly
  on their rookie-draft position. Veterans: 4,493 snapshots of 1,487 players, 543–596 per offseason.
- **Resampling detail.** A resampled veteran counts once per draw in the ±10% count; "fewer than 10" uses that count.
- **Crash-test results (7 Nov, `study/out/pick_values_crash.json`, 1,000 resamples per run).** Leak checks passed.
  Fair world: range included 1.0 in **200 of 200** (bar 90%); typical R 1.01, typical range width 0.45. Tilted 0.7:
  range excluded 1.0 in **167 of 200 = 83.5%** (bar 80%); typical R 0.71. Tilted 1.3: excluded in 49 of 50; typical
  R 1.31. **PASS.** Read plainly: the study can see a 30% tilt about five times in six, and the fair-world ranges
  are on the cautious side (never a false alarm in 200). A tilt of 10–15% could well be missed; a fair verdict means
  "within roughly ±25%", not "exactly fair".

**After lock**

_None yet._
