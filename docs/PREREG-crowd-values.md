# PRE-REGISTRATION — Crowd Values From The Vote Page

**Written:** 11 November 2026. **Status: LOCKED** by the commit that adds this document with `study/crowd_values.py`,
its two frozen data files and the simulation results, before any vote has been read for this purpose.

**Steve's calls, 11 Nov:**

- "yes I agree with you on 1, let's do it for order only": the crowd sets the order, and DELTA's history sets the
  price of each spot.
- "I think the 20% cap sounds right."
- Gimme check yes; no speed penalty ("The chooser is set up for quick picking").
- 30 votes before a player gets a value.
- "keep the trade calc as it currently is for a while until we can import the whole new system over."

---

## Plain-English Summary (For Steve)

**What the votes decide.** The order: who the crowd would rather have, and where it's a coin flip.

**What they don't decide.** How much each spot in line is worth. That comes from DELTA's own value curve, which is
built from history and frozen today: the 1st spot is 10,000, the 10th about 7,900, the 50th 3,420 and the 150th 820.
If the crowd puts Bowers 8th, he gets the 8th spot's price. No market numbers are used anywhere.

**When it's usable.** A player needs 30 real votes. The board is called "steady" once two random halves of the voters
produce boards that agree at 0.85 or better. That's a progress marker only: the Trade Calc doesn't change.

## 1. The Data

- **Source:** `vote_picks` in Supabase, exported as a CSV from the Table Editor. The columns are the ones in
  `supabase/vote-picks.sql`.
- **The board:** `study/data/crowd-board-2026-11-10.json`, the 159 items exactly as `vote/index.html` serves them. That
  is DELTA Value's top 150 (12-team superflex, full PPR, 10 Nov) plus nine 2027 pick tiers, each with the slot the page
  pairs by.
- **Skips** (an empty pick) are counted and reported, never used in the fit.
- **Votes for players not on the board** are left out. A future board gets a new `board` value and its own run.

## 2. Weights

1. **Gimme check.** A device that has seen at least 3 gimme pairs and missed more than 1 in 3 has all its votes count
   half. A miss is picking the side with the worse page slot.
2. **No speed penalty.** The time per pick is stored but never used.
3. **Owner cap.** For each player, the weight of owner-tagged votes involving him is scaled down, if needed, to at most
   20% of all the weight on that player. A vote between two players takes the smaller of their two scale factors.
4. **Everything else counts 1.**

## 3. The Fit And The Board

- **Strengths:** a weighted Bradley-Terry fit, which finds the strengths that best explain every pick at once.
  - Each item also plays one pretend win and one pretend loss against an average item, so a player who has won every
    vote so far doesn't run off to infinity.
  - It's solved with the standard iterative method until it stops changing.
- **Who gets a value:** an item with at least **30** real (non-skip) votes, of any tag.
- **Order:** qualifying items sorted by strength.
- **Price:** the k-th qualifying item gets the k-th entry of `study/data/crowd-price-list-2026-11-10.json`.
  - That list is DELTA's new value for its 372 site players (2026 week 9, full PPR, 12-team superflex, Contract
    Security on), sorted, with the top at 10,000.
  - Only the prices are used; no player's own value is.
  - Picks share the same price list.
- **Everyone else** shows "Not Enough Votes Yet" with their vote count.

## 4. Steadiness (A Progress Marker, Deciding Nothing)

- Split the devices into two random halves, 200 times.
- Fit a board from each half, and measure the rank agreement over items that qualify in both halves. Splits with fewer
  than 10 such items are skipped.
- **Steady** means the median agreement is at least **0.85**. The Trade Calc stays on its current values regardless
  (Steve, 11 Nov).

## 5. Reported With Every Run

- Votes and skips.
- Devices.
- Votes by tag.
- Devices put on half weight by the gimme check.
- Items with a value.
- Steadiness.
- The board itself (`study/out/crowd_board.csv`).

## 6. Simulation Before Lock (`study/out/crowd_values_simulation.json`)

**The planted world:** a known true order, where strength falls with the page slot. Voters pick by that truth plus
noise. Pairs are drawn as the page draws them, over 150 devices.

| Votes | Items With A Value (Of 159) | Agreement With The Truth | Two Halves Agree |
|---|---|---|---|
| 1,000 | 0 | — | — |
| 2,500 | 94 | 0.91 | — |
| 5,000 | 159 | 0.96 | 0.87 (steady) |
| 10,000 | 159 | 0.99 | 0.94 |

**Read it as a best case.** Real voters disagree more than this planted crowd does, so expect to need more votes than
the table says. Even so, the first full board needs about 5,000 votes.

## 7. Prior Looks

- No vote has been exported or read for this study.
- Steve has voted on the page (about 150 of the first 600 votes) and has seen its pair percentages. That is how the
  page works, and his votes are capped by §2.

## 8. Not Licensed Here

- **The Trade Calc:** unchanged.
- **The site, the DELTA Score and the Own Value Scale.**
- **A new board, recency weighting, or adaptive pairing.** Each needs its own dated amendment before it's used.

## 9. Amendments

None.
