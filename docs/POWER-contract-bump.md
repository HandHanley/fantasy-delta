# Power Check — Could History Measure A Contract Bump? (9 Nov 2026)

**Asked by Steve, 9 Nov:** "I do think we should do the test to figure out how big the bump would be for contracts - I
don't want to arbitrarily set a percentage." Then: "lets do the contracts power check." No contract data was used: every
contract here is made up.

## What Was Done

`study/ovs_contract_power.py`, results in `study/out/ovs_contract_power.json`.

1. **Made-up contracts.** Every veteran from 2001–2022 got simulated deals: a length, counting down a year per season,
   then renewing. Each player-season falls in one group: contract year, 1 year left, or 2+ years left.
2. **A planted bump.** Contract-year players' next three seasons × (1 − b), and 2+ years × (1 + b).
3. **The method.** Each veteran's value (the adopted preseason value) is scaled by his group's history: outcome ÷ value
   over seasons whose results are in.
4. **The usual test.** At least 2% better on the 5,693 veteran test rows (2013–2022), paired permutation p < 0.05.
   40 simulations per bump size.

## Results

| Planted Bump | Times The Test Passed (Of 40) | Typical Improvement |
|---|---|---|
| ±3% | 0 | −0.3% |
| ±5% | 0 | −0.3% |
| ±7.5% | 0 | −0.1% |
| ±10% | 0 | 0.1% |
| ±15% | 0 | 0.7% |
| ±20% | 2 | 1.2% |

**How precisely all of history (2004–2019) would pin the bump down (90% range):**

| True Bump | Measured As |
|---|---|
| 0 | −5% to +3% |
| ±5% | +2% to +9% |
| ±10% | +6% to +12% |

## What It Means

- **A contract bump can never pass the 2% accuracy bar**, even a large and completely real one, and however much history
  we collect.
  - The reason: a player's next three seasons swing so widely that nudging values by a few percent barely changes the
    typical miss.
  - This holds for any small across-the-board layer, not just contracts.
- **History could measure the size, to within about ±4 points.** With a full contract history, a true 10% bump would be
  measured somewhere between 6% and 12%. That is a measurement with a range, not a pass/fail test.
- **The decision is Steve's:**
  - collect the history and use the measured size as a labelled layer, as a stated exception to the 2% rule; or
  - leave contracts out.
