# PRE-REGISTRATION — Should You Sell A Breakout Rookie?

**Written:** 28 September 2026. No outcome has been looked at: the only runs were `--count` and a
listing of who counts as a breakout — both from **rookie-year prices only**, the information a manager
has when deciding to sell — and a crash test with every year-two price replaced by random numbers
(proves the code runs — nothing more). **Disclosure:** these seasons' prices were used on 26 Sep for a
different question (does DELTA's in-season read predict price moves; rookies +1.0%, reported only).
Whether breakout rookies give value back has not been looked at.
**Status:** locks on commit. **Script:** `scripts/rookie-sellhigh-study.py`.

---

## 1. The Owner's Question

"If a rookie is exploding, it is almost always worth selling" — Stroud, LaPorta, Brian Thomas Jr.
went off as rookies and came back down; Puka Nacua is the exception. For a dynasty platform, a sell-high
signal on rookies would be one of the most useful things DELTA could say — **if it is real.**

**Why test rather than trust the examples:** the rookies who faded are memorable; the ones who kept
going (Jefferson, Chase, St. Brown) are easy to forget. Only the whole record answers it.

---

## 2. The Test

- **Rookie classes 2020–2024** (the 2025 class has no end-of-year-two price yet). Rookies = drafted
  QB/RB/WR/TE with a DynastyProcess superflex price before their first Week 1 (347 players).
- **Breakout** — decided from price only, at the sell point: **top 20% of his class by price rise since
  before Week 1, and in the top 150 players by market value at the sell point** (all positions). The
  second condition was added before any outcome was read, after rookies rising from near zero (Jaren
  Hall 3 → 108) qualified on rise alone — the owner's rule that signals should be about players who
  matter in lineups.
- **Sell point — primary: the end of the rookie regular season.** Reported: after Week 8, and the next
  preseason.
- **Outcome:** his price change from the sell point to **the end of his second regular season**,
  compared with the other rookies in his class. Prices as `log(value + 100)`; a player missing from a
  snapshot counts as 0.
- **Range:** 2,000 bootstrap resamples, seed 20260928.

| If, at the end-of-rookie-season sell point… | Verdict |
|---|---|
| breakouts' change minus others' is below zero across the 95% range, **and** breakouts lose value on average | **Supported** — sell high is right |
| below zero across the range, but breakouts do not lose value on average | **Relative only** — they grow slower than other rookies, but holding did not lose value |
| the range reaches zero or above | **Not supported** |

**Reported only:** the other two sell points; the share of breakouts that lost value; whether bigger
rises are followed by bigger falls; every breakout by name with his outcome.

**Stated in advance so it can be wrong:** "relative only" — the market cools on breakouts, but year-two
prices for good young players usually hold.

---

## 3. What It Could Lead To

**Supported:** a design for a **"Sell-High Window"** flag on breakout rookies (DELTA's watch colour),
then Study 2 (what separates the Pukas from the fades) to say *which* breakouts to sell. **Relative
only:** a softer signal — "his value has likely peaked relative to his class". **Not supported:** no
flag; the record is published. **This study changes nothing in the engine.**

---

## Pre-Lock Checks (28 September 2026)

| Check | Result |
|---|---|
| Prices, dates, ID links | Imported from `scripts/market-form-study.py` (verified 3,370/3,370 prices; links checked by hand) |
| Snapshots | All within 5 days of the target except class 2020's season end: 31 Jan 2021, 28 days late (archive gap) — allowed, disclosed |
| Breakout lists (rookie-year prices only) | 2023: Nacua, Dell, LaPorta, Rice, Achane, Reed, Spears, Downs, Levis, Stroud · 2024: Irving, Tracy, Nix, Brian Thomas Jr., McMillan, Allen, McConkey, Bowers, Davis, Maye, Penix, Wright |
| Counts | 347 rookies (2020 67 · 2021 64 · 2022 68 · 2023 76 · 2024 72); breakouts: after Week 8 47 · season end **57** · next preseason 59 |
| A bug the crash test caught | A table method called on a plain array — fixed before locking |
| `--run` refuses while this file is uncommitted | Refused |

---

## Amendments

*(none)*
