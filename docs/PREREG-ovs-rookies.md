# PRE-REGISTRATION — Own Value Scale: Incoming Rookies On Draft-Slot Averages

**Drafted:** 8 November 2026. **Status: DRAFT, NOT LOCKED.** Steve: "Let's do rookies first." Locks by committing this
document with `study/ovs_rookies.py` and its crash results, before the one real run.

---

## Plain-English Summary (For Steve)

**Today:** an incoming rookie is valued from the 30 past rookies closest to him in draft slot and age.

**The alternative:** the plain average of every past rookie at his position drafted in the same range (picks 1–10,
11–32, 33–64, 65–105, 106+), all counted equally.

**Why:** in the first Own Value Scale study, that plain average was the better guide for incoming rookies (typical
miss 84.3 vs 87.4 on five seasons).

**The test:** on rookies from 2013–2022, does the plain average predict their first three seasons at least 2% better?

## 1. The Change, And Only The Change

- **Incoming rookies (draft-day snapshots):** value = the average three-season outcome (FV3) of the pool players in his
  position, same draft range and same career stage, from `comps_value_study.py`'s B3 bands, unchanged (a band below 30
  players widens to the neighbouring career stage, then the neighbouring draft range). Pool `≤ t − 3`, as everywhere.
- **Everything else is the adopted value:** era-adjusted veteran matching, three seasons ahead, offseason changes
  (`docs/PREREG-ovs-offseason.md`). Veteran predictions are identical in both versions.
- **Rows:** 791 incoming rookies, 2013–2022 (all drafted; median band 120 players).

## 2. The Questions

- **Decides:** RMSE on FV3 over the 791 rookie rows, bands vs matches: at least **2% better**, paired permutation
  p < 0.05 (10,000 shuffles); **and** all 6,484 rows no more than 0.5% worse; **and** close synthetic trades no more than
  1.0 point worse.
- **Decision:** passes → incoming rookies are valued on draft-slot averages (Steve's OK). Fails → rookie matches stay.

## 3. Reported, Deciding Nothing

By position; a half-and-half blend of the two; the 2026 rookies' values both ways.

## 4. Prior Looks

- `PREREG-own-value-scale.md` §13: on five seasons and the locked matching, draft-slot bands beat OVS for incoming
  rookies, 84.3 vs 87.4. That is these rookies on a longer outcome; the three-season comparison has not been computed.
- The adopted value's veteran results are known.

## 4b. Crash Tests, Before Lock

The era study's worlds with this rule: noise passes in at most 1 of 20; planted w = 0.75 passes in ≥ 80% of 200; w = 0.6
reported. Leak checks asserted (bands read only finished windows `≤ t − 3`; a rookie is never in his own band).

## 5. Limits

- Draft slot and position only: no age, college production or landing spot (each its own study).
- Equal weights across 2001–(t − 3); no recency weighting.

## 6. Not Licensed Here

The DELTA Score, the site's model value, buy/sell calls. Nothing on the site changes.

## 7. Amendments

**Crash tests (8 Nov, `study/out/ovs_rookies_crash.json`): FAIL.** Noise world 1 of 20 (at the limit, passes). Planted
w = 0.75: **97 of 200 (48%, bar 80%)**, typical lift 2.1%. w = 0.6: 4 of 50. Both methods lean mostly on draft slot, so
their rookie values are close; with 791 rookies the test can't reliably separate a gap near 2%. Per §4b this goes to
Steve before any real result. Nothing has been run.
