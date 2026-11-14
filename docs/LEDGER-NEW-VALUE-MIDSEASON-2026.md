# New Value Mid-Season Freeze, 2026 — Pre-Registration

**Written 13 November 2026, before the freeze file exists.** Approved by Steve the same day ("let's do all of that and
let's capture KTC and FC"). A second ledger alongside `docs/ACCURACY-LEDGER.md`, which keeps its own rules and its own
September freeze untouched.

---

## 1. Why A Second Freeze

The 7 September freeze (`data/freeze-2026.json`) graded what the site showed this season: the DELTA Score, projected
PPG and model-value calls. It stays, and is graded in February 2027 as planned.

New Value (the own value scale, `study/new_value_weekly.py`) is a different claim, built this autumn and meant to
replace DELTA Value. This freeze records what it said on one day, so it can be graded on what happens after.

## 2. What New Value Claims

One number per player on a 1–10,000 scale: his value over the **next three seasons (2027, 2028, 2029)**, in a 12-team
superflex full-PPR league. The target, as built (`comps_value_study.outcome`, horizon 3):

> FV = Σ over k = 1..3 of 0.9^(k−1) × max(0, his season points in 2026+k − the starter line at his position that
> season), full PPR, lines QB24 / RB34 / WR48 / TE14 (`C.REPL_N_FULL_ADOPTED`).

It is **not** a 2026 points projection, so the September ledger's Test 1 has no counterpart here.

## 3. What Gets Frozen

`data/freeze-2026-nv-midseason.json`, written once by `scripts/freeze-new-value.py`:

- **New Value, verbatim:** `data/new-value.json` as committed by the New Value Weekly run of 13 Nov 2026
  (run 43479685276; through week 9; 884 players and the 2027 pick values), byte for byte, with its SHA-256.
- **FantasyCalc, 12-team superflex, full PPR:** the `12|sf` list from `data/market-values.json` as committed
  13 Nov 2026 (FantasyCalc poll 15:30 UTC), with that file's SHA-256 and commit.
- **KeepTradeCut, superflex:** fingerprint only in the public file (repo, path, upstream commit and date, SHA-256 of
  the bytes). The values are kept in the owner's private Claude Project, as with the September comparators, because
  KeepTradeCut's terms bar using its data on another website. Source: `github.com/dachhack/stathead`,
  `public/data/ktc_rankings_superflex.json`, committed upstream 13 Nov 2026 14:18 UTC; `superflexValue` is the basis.
- **Provenance:** the commit that built New Value, the freeze script's SHA-256.

Names are stored verbatim from each source and **not** joined to each other. Joining happens at grading time with the
engine's own normaliser, so a miss stays visible.

**Timing, recorded honestly.** One game had been played in week 10 (Thursday 12 Nov) before both market captures.
New Value runs through week 9 and has not seen it. The markets have a one-game head start; it is small, and Test A
counts no 2026 games at all.

## 4. The Tests

### Test A — Ranking The Next Three Seasons (Market-Blind), Head To Head

- **Players:** QB/RB/WR/TE in New Value and in both markets at freeze. Picks are not graded here (Stage 1's history
  study covers them).
- **Outcome:** each player's FV (section 2), computed from final season data. A player who retires, is cut or is
  injured scores what he scored; nobody is dropped for not playing.
- **Measures, for New Value, FantasyCalc and KeepTradeCut on the identical player set:**
  1. Rank correlation (Spearman) with FV, overall and within each position.
  2. Top-N hit rate: of each source's top 24 / 50 / 100, how many finish top 24 / 50 / 100 by FV.
  3. Head to head: New Value's correlation minus each market's, with a bootstrap 95% interval over players.
- **When:** partial reads after the 2027 season (one of three seasons) and the 2028 season; **final in February
  2030**, after the 2029 season.

### Test B — Does The Market Move Toward New Value? (Market-Relative)

- **Players:** QB/RB/WR/TE in New Value and the market, inside either one's top 200 (ranked within that common set).
- **The call:** gap = market rank − New Value rank. **Buy:** New Value ranks him 30+ places higher than the market.
  **Sell:** 30+ places lower. Everyone else: no call.
- **Outcome:** the change in his rank in that same market, from the freeze to the market's snapshot on the **Sunday
  before Week 1, 2027** (repeated 2028, 2029). FantasyCalc from DELTA's own daily `market-values.json`; KeepTradeCut
  from the same third-party archive at that date. A player who drops out of the market's list counts as falling to
  its bottom.
- **Measures, per market:** average rank change of buys minus sells (positive = the market moved toward New Value);
  share of buys that rose and sells that fell; a permutation test shuffling the buy/sell labels within position.
  Overall rank is primary (New Value is one cross-position scale); positional rank is reported beside it, as in the
  September ledger.

### Not Tested

- **2026 points.** New Value makes no 2026 claim.
- **The crowd board.** DELTA's own vote market had about 1,100 votes on 12 Nov, too few to price anyone. It is not a
  comparator in this freeze.

## 5. Rules

1. **The freeze file is never edited, regenerated or corrected.** If New Value was wrong, the ledger says so.
2. **The live New Value keeps changing** (weekly builds, future model changes). The freeze does not.
3. **The comparator list is closed:** FantasyCalc and KeepTradeCut, as above. Nothing is added because it scored well
   or dropped because it scored badly.
4. **Measures are fixed by this document.** Anything added after a result is seen is recorded as added later, and
   why.
5. **One freeze is not a verdict.** As in the September ledger, the signal is in the trend across freezes. The first
   true pre-season test of New Value is the September 2027 freeze.

## 6. What Was Not Done, And Why

**No "pre-season" New Value freeze built today with 2026 games removed.** New Value was shaped this autumn while
2026 was being played: the first version was rejected partly on how players were performing, and the starter lines,
contract security and roster share were chosen in November. A pre-season version built now would carry that
hindsight and could not honestly be called a freeze. It may be built as a private, labelled hindsight check; it is
never part of this ledger.

## 7. Timeline

| When | What |
|---|---|
| 13 Nov 2026 | This document committed, then the freeze file, then its OpenTimestamps proof. Before Sunday's week 10 games. |
| Sunday before Week 1, 2027 | Test B, first read (both markets). |
| February 2028 | Test A, partial (2027 season). |
| Sunday before Week 1, 2028 | Test B, second read. |
| February 2029 | Test A, partial (2027–2028). |
| Sunday before Week 1, 2029 | Test B, third read. |
| February 2030 | **Test A, final** (2027–2029). |

---

## 8. Version 1 Withdrawn, 13 November 2026 (Before Any Outcome)

Dated entry, added under rule 4. **`data/freeze-2026-nv-midseason.json` (version 1) stays in the repo exactly as
written: never edited, never deleted.** It is withdrawn as the graded freeze, and a version 2 replaces it.

**Why.** Within an hour of the freeze, Steve spotted Tyreek Hill as its top buy: no NFL team, no game in over a year.
The cause was systemic, not a ranking anyone disagreed with. New Value sees only on-field production, so players on
no NFL roster were valued off last season as if active (Taysom Hill 64th, Tyreek Hill 77th, Philip Rivers 195th; 50
veterans in all), and a cut, unsigned rookie kept his draft-slot value (Damien Martinez 170th). A second bug left out
eight rookies whose first game came after the build's week (Robert Henry Jr. among them).

**Why a replacement is honest here.** Rule 1 exists to stop a freeze being changed after its results are seen. None
exist: Test A counts 2027–2029 games and Test B first reads in September 2027. The fixes are general rules, not
player edits, and were decided from history and Steve's standing rule, not from any outcome:

1. **No game this season and on no NFL roster** (any team, any status but cut or retired, injured reserve and practice
   squads included) **→ no New Value until he signs.** History, 2016–2022: former fantasy starters in that position
   played again 6% of the time and were starters again 3% (all three were un-retiring stars); on a roster, 47% and
   13%. Applied to never-played rookies too (not separately measured).
2. **"Has played" counts games up to the build's week only.**

Both are in `study/new_value_weekly.py`. Checked on the same week-9 data: every remaining player's value is unchanged.

**What was not changed.** Injured players on a roster (Trey Benson, James Conner, Jayden Higgins, Ricky Pearsall) keep
their values: DELTA does not penalise injury. Steve's view that Benson and Conner have lost their role to Jeremiyah
Love is a disagreement with the model's call, not a missing fact, so it is left for the freeze to grade (and for a
possible later study of a teammate taking over a role).

**Version 2.** Built by the weekly run with week 10 data, eye-tested by Steve (top 50, all buys and sells) before it
is written, frozen before Thursday 19 November's game as `data/freeze-2026-nv-midseason-v2.json`, with FantasyCalc and
KeepTradeCut captured fresh that day. Sections 2–7 apply to it unchanged; its dates replace version 1's. **At grading,
version 2 is the result; version 1 is reported beside it**, so the withdrawal hides nothing.

## 9. Version 2: What Changed Before Freezing (13 November 2026, Before Any Outcome)

Dated entry, added under rule 4, while version 2 is unfrozen. No outcome exists: Test A counts 2027–2029 games, and
Test B's first reading is the Sunday before Week 1, 2027.

**New Value rules added since section 8** (all in `study/new_value_weekly.py`, each with its own write-up):

- A practice squad counts as no team for a player with no game this season (history: 0 of 151 veterans and 1 of 301
  rookies became fantasy starters). Whether he has a team reads his latest row in the weekly roster file.
- Rookies keep their draft-slot value until 150 offensive snaps (`PREREG-ovs-rookie-snaps.md`).
- Tested and **not** adopted: capping each match at the third-best (`PREREG-ovs-one-match.md`, 1.77% vs the 2% bar) and
  a roster-spot cost (`DECISION-roster-spot-cost.md`, moved no one more than 6 places).

**Test B's call rule is replaced.** Steve's eye test of the "30 places apart" calls found them dominated by long shots
past 120th, where every player is worth close to nothing and rank gaps are cheap, and by a running back vs receiver
tilt that any dynasty player already knows. Steve, 13 Nov: "This definitely looks better." The new rule:

- **Within position.** QB, RB, WR and TE are each ranked separately: New Value's order and the market's order, among
  players in both (the common set at that position).
- **Value at stake** = his New Value − New Value's value for the player at the market's position rank. Both numbers
  are on New Value's 1–10,000 scale, so the market's own scale doesn't enter.
- **The pool:** players inside either one's overall top 200 (as before).
- **A call:** value at stake **+1,000 or more → buy; −1,000 or less → sell** (10% of the top player, about the value of
  the 150th-best player). Everyone else: no call.
- **No call on a season-ender:** anyone on `data/injury-overrides.json` on freeze day (Steve's hand-kept, confirmed
  list) gets no call either way. Their values are unchanged (no injury penalty); they're listed in the freeze and
  reported, not graded.
- **No call until 150 snaps:** a rookie still on his draft-slot value (no game, or under 150 offensive snaps; listed in
  the build's `meta.rookie_snap_rule`) gets no call either way. His value is a draft slot, not demonstrated production,
  so a call would be a call on draft capital (Steve, 13 Nov: "I love the no call until 150 snaps rule"). On 13 Nov
  markets this removed Ty Simpson, Jadarian Price, Marlin Klein, Drew Allar, Kaelon Black and Oscar Delp from the
  buys and nobody from the sells. Listed in the freeze and reported, not graded.
- **Outcome:** the change in his **position rank** in that same market, freeze to the Sunday before Week 1 (2027, 2028,
  2029). A player who drops out of the list falls to the bottom of his position. Measures as section 4: buys' average
  move minus sells', share moving the right way, a permutation test shuffling labels within position.
- **Reported beside it, deciding nothing:** the "30 places apart" overall calls as written in section 4, so nothing
  about the old rule is hidden.

**Prior looks.** The 1,000 line was proposed from a stated reason before its calls were listed, and the counts it
gives (not the names) were shown first; Steve then saw the lists on 13 Nov markets. Nobody has seen any market move
after 13 Nov.

**Freeze date.** Held for the role-change study (Steve, 13 Nov). Version 2 freezes once that study is decided and Steve
eye-tests the build, with FantasyCalc and KeepTradeCut captured the same day, before the season's last regular-season
game. Section 8's "before Thursday 19 November" is replaced by this.
