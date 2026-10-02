# PRE-REGISTRATION — The Pedigree Gap: Does The Market Weigh Draft Slot Right After Year One?

**Written:** 29 September 2026. No outcome has been looked at: the only runs were `--count`, group
listings from rookie-year stats and draft slot, an overlap count against Study 1, and crash tests with
every outcome price replaced by random numbers (they prove the code runs — nothing more).
**Status:** locks on commit. **Script:** `scripts/pedigree-study.py`.

---

## 1. The Question

DELTA's August draft-capital study found that for young players the best forecast **blends** draft slot
and production, with draft slot outweighing a player's own numbers until about **a season and a half**
of games (K = 24). So after year one, a disappointing high pick should be expected to recover somewhat,
and a late-round producer to cool somewhat. **Does the market price that correctly?**

- **Decision point:** the last price before the player's **second** season — when dynasty managers buy
  and sell.
- **Outcome:** his price change from there to the **end of his third regular season** — a window no DELTA
  study has used.
- **Classes 2020–2023** (DynastyProcess superflex prices; four classes have a year-three end).

---

## 2. The Groups

- **The Name — primary.** A round 1–2 pick whose rookie points per game were in the **bottom half** of his
  class's drafted rookies at his position (games by the live DNP rule; half PPR + TE premium).
- **The Producer — reported only.** A round 3+ pick in the **top third**. **Why only reported:** 22 of its
  38 players were Study 1 breakouts whose year-two prices have been seen (St. Brown, Stevenson and
  Pacheco soared; Pierce, Dell and Dulcich collapsed). The year-three window is new, but a year-three
  price follows the year-two price closely, so this half of the test is not clean evidence. The Name
  overlaps Study 1 by 1 player (AJ Dillon).

---

## 3. The Test — Price-Matched

A group's result is its average gap to **rookies who were priced the same at the decision point**: a line
fitted on all other rookies (price change vs starting price), then the group's average distance from
that line. **Why:** in the first crash test, random prices made The Producer look "overpriced" only
because higher starting prices fall and lower ones rise on noise. After the fix, three random-price runs
all read "priced about right" for both groups. Range: 2,000 bootstrap resamples, seed 20260929.

| The Name's 95% range… | Verdict |
|---|---|
| entirely below zero | **Market overprices disappointing high picks** — a sell-the-name signal |
| entirely above zero | **Market underprices them** — a buy-low-on-pedigree signal |
| crosses zero | **Priced about right** |

**Honest limit:** The Name has only **16 players**. Only a large mispricing can be confirmed; "priced
about right" may just mean "too few to tell".

**Stated in advance so it can be wrong:** priced about right — too few players to show anything else.

---

## 4. What It Could Lead To

A clear verdict on The Name becomes the basis for a **buy-low** or **sell-the-name** design for
second-year players, needing a forward check before it ships. **This study changes nothing in the
engine.**

---

## Pre-Lock Checks (29 September 2026)

| Check | Result |
|---|---|
| Snapshots | Decision point and outcome within 5 days of target for every class |
| Groups (rookie-year stats + draft only) | The Name e.g. 2022 Jameson Williams, John Metchie III, Skyy Moore; 2023 Quentin Johnston, Jonathan Mingo, Luke Schoonmaker, Brenton Strange, Marvin Mims Jr. |
| Counts | 270 rookies priced at the decision point (2020 62 · 2021 66 · 2022 72 · 2023 70); The Name 16; The Producer 38 |
| Overlap with Study 1 breakouts | The Name 1 of 16; The Producer 22 of 38 (reason it is reported only) |
| A flaw the crash test caught | Plain group-vs-rest gap read noise as mispricing → price-matched comparison |
| `--run` refuses while this file is uncommitted | Refused |

---

## Amendments

*(none)*

## Result (29 September 2026) — PRICED ABOUT RIGHT

Run once, `python3 scripts/pedigree-study.py --run`, against this file as committed in `f783384`
(sha256 prefix `a2ffcadaa3cac2cc`). Nothing above this section was changed after the run.

| Group | n | Price-Matched Gap | 95% Range | Verdict |
|---|---|---|---|---|
| **The Name (primary)** | 16 | +11.1% | −35.8% to +88.3% | **Priced about right** |
| The Producer (reported only) | 38 | +11.9% | −23.2% to +67.0% | Priced about right |

The stated expectation was right. **The ranges are enormous** because outcomes swing wildly within each
group — The Name runs from Trey Lance −95% to Brenton Strange +609%; The Producer from Dameon Pierce −94%
to Nico Collins +1,195%. Neither draft pedigree nor rookie production, used this way, points the market
wrong in a way these samples can show.

**Across the rookie studies (1, 2, the volume check and this one):** the dynasty market prices rookies'
draft slot, rookie production and the sophomore slump about right on average; what it cannot foresee,
neither can these simple rules. A DELTA edge on rookies, if one exists, has to come from information the
market weighs less — for example DELTA's own college data (dominator, breakout age), which has not been
tested against rookie outcomes beyond draft capital. **This study changes nothing in the engine.**

## Record Correction (1 October 2026)

The Result above gives the locked file's sha256 prefix as `a2ffcadaa3cac2cc`. That value was not produced by the
run and matches no version of any pre-registration ever committed. The Result correctly names the
lock commit, `f783384`; this file at that commit has sha256 prefix **`c34670196cc8e8ae`**. Only the fingerprint was
wrong — the outcome above is unaffected. Nothing above this section was changed.
