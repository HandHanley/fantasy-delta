# DECISION — Contract Security: QBs In A Contract Year Use The QBs' Own Measured Number

**Decided:** 26 November 2026, by Steve. **Status: APPLIED** to the weekly New Value build (`study/contract_layer.py`,
`study/new_value_weekly.py`). **A judgment, not a passed test.**

## What Changed

A QB whose deal ends after next season, or sooner, is multiplied by **×0.868** instead of the all-positions **×0.769**.
Every other position, and QBs with more years left (×0.955, ×1.078), are unchanged.

## Where ×0.868 Comes From

The contract study's own QB result (`study/out/ovs_contract_security_results.json`, `reported.by_position.QB`,
`group_0`): QBs in a contract year delivered 0.868 of their expected value, against 0.745 for all positions. It was
reported 10 Nov and decided nothing then. It is not a number picked to fit.

## Why It's A Judgment

- With 63 QB contract years, the QB number's 95% range runs from about 0.50 to 1.24, so the data can't show that QBs
  differ from the average.
- Two tests made on 25–26 Nov couldn't settle it either:
  - **The one-year vs multi-year split** (`PREREG-contract-length.md`): the crash test failed (a planted 0.25 gap was
    caught 26 times in 200).
  - **Each position pulled toward the average by its own uncertainty** (standard partial pooling, on the same reported
    numbers): QB came out at ×0.74.
- Steve's reasoning (26 Nov): "we know that Stroud and Lamar will be starting QBs next year regardless of what team,
  so a 23% cut does seem a bit too harsh." Contract-year QBs kept about 89% of the starts their comparables got.
- Steve, on the result: "I don't agree with this list 100% but I can at least see the argument for each ranking."

## Effect (Week-11 Build)

21 QBs move up about 13%; nobody else moves. Lamar Jackson 3,871 → 4,366, C.J. Stroud 3,540 → 3,992, Bryce Young
2,382 → 2,687. Checked by rebuilding week 11 locally: only QBs on a contract-year multiplier changed, and the top
player's raw value (the scale) is unchanged.

## Revisit

Each finished season adds about six QB contract years. Re-measure when the contract table is extended, and replace this
with a measured QB number if one can be shown.
