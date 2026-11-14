# DECISION (PROPOSED) — New Value: A Dead-Weight Season Costs A Roster Spot

**Drafted:** 13 November 2026, before the cost has been measured or applied to anyone. **Status: LOCKED** by
committing this document with `study/ovs_roster_cost.py`; the measurement and the safety check run after.
Steve, 13 Nov: "I really like the long shot costs a roster spot idea. That kind of brings the opportunity cost into
the equation." League size: "about 28 and don't account for IR or taxi."

---

## Plain-English Summary (For Steve)

**Today,** a season where a player doesn't reach the starter line counts as zero. A long shot with a 6% chance of
hitting is all upside: his busts cost nothing.

**The change:** a season where he plays but doesn't reach the starter line costs the price of a roster spot. A star
rarely pays it. A long shot pays it most years, so his value now has to cover carrying him.

**The price of a roster spot** is what the spot would have given you with someone else in it: the starter points that
the last players on rosters (a 12-team league, 28 each, 336 players) actually went on to produce in a season. It's
measured from 2006–2012, so the seasons it's checked on (2013–2022) don't set it.

**Why this isn't the usual 2% test.** This changes what New Value measures (starter points minus the cost of carrying
him), not how well the model guesses. Like the starter lines (`DECISION-replacement-lines.md`), the number is
measured from how leagues work, set by a formula fixed here before anyone's value is seen, then checked so it can't
make DELTA worse at ranking who actually produced.

## 1. The Outcome, Changed

For a player at season t, over t+1..t+3 (discount 0.9, as today), on the starter line for the scoring in use. The
study runs on the frame every New Value study uses (half PPR + TE premium, lines QB24 / RB30 / WR42 / TE14; checked:
recomputing FV from the season file on those lines reproduces the frame's FV exactly). The weekly build uses full
PPR and QB24 / RB34 / WR48 / TE14.

- Today: FV = Σ 0.9^(k−1) × max(0, points − line).
- **New: FV_rc = Σ 0.9^(k−1) × [max(0, points − line) − c × dead].** dead = 1 if he played at least one game that
  season and scored under the line; otherwise 0.
- **Not charged:** a season with no games. He's out of the league (you'd cut him) or hurt all year (no injury penalty).
- A season shortened by injury that falls under the line **is** charged. It's what happened on the field, as FV
  already counts it. Recorded as a known edge.

Values stay the recency-weighted average of the 30 matches, now over FV_rc. A value can go below zero.

## 2. The Price, c (One Number, All Positions)

- Week-9 frame rows (`ovs_small_samples`), seasons t = 2006–2012 only.
- In each season t, rank every row by today's live value (the in-season value, with the rookie draft-value rule).
  The rows ranked **301st–336th** are "the last players on rosters" (the bottom 36, three per team).
- c = their average FV ÷ (1 + 0.9 + 0.81): starter points per season, the same units as one season of FV.
- **For the weekly build,** the same 36-per-season players' seasons are rescored in full PPR on the build's lines, and
  c_display is their average the same way. Same players, the build's scoring.
- Both computed once and printed. Nothing is tuned after.

## 3. Safety Check

On test rows 2013–2022 (6,808): rank correlation (Spearman) between values and **today's FV** (starter points, what
the September and mid-season ledgers grade). New must be no more than **0.01 lower** than today.

## 4. Reported, Deciding Nothing

- c, and the rows behind it.
- Rank correlation with FV_rc, both ways.
- Late-round rookies on draft value and the bottom of the board: produced ÷ value.
- **This week's build:** the top 200 and the buy/sell lists (both "places apart" and "value at stake") for Steve's
  eye test.

## 5. Then

Passes the safety check and Steve's eye test → the weekly build uses FV_rc, and the freeze version 2 ledger grades
both FV and FV_rc. Fails either → no change.

## 6. Prior Looks

The 13 Nov late-round rookie and one-match results (`PREREG-ovs-one-match.md` §5, §8). No FV_rc has been computed.

## 7. Results (13 November 2026)

`study/out/ovs_roster_cost_results.json`; this week's build rerun with FV_rc (`/tmp/diag/nv_roster_cost_build.py`,
not shipped).

- **The price of a roster spot is small:** c = 1.14 starter points per season (study scoring), 1.66 (full PPR). The
  252 players ranked 301st–336th in 2006–2012 averaged that because only 6% of them ever produced starter points. The
  alternative to a long shot is another long shot.
- **Safety check passed:** rank correlation with FV 0.537 → 0.529 (drop 0.008, allowed 0.01). It got slightly worse
  and gained nothing.
- **It barely moves anyone:** in this week's build no top-200 player moves more than 6 places. Klein 127 → 128,
  Benson 125 → 125, Kaliakmanis 157 → 155, Barion Brown 185 → 182. The buy lists are almost unchanged (FantasyCalc 63
  → 62). The players just above and below the long shots are steady part-timers who are also under the line most
  seasons, so they pay the same charge.
- **Decision: no change.** Recorded as a finding: on DELTA's own history, carrying a long shot costs little, because
  every bench spot is a long shot.
