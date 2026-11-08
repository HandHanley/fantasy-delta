# PRE-REGISTRATION — Own Value Scale: True Peers For Elite Players

**Drafted:** 8 November 2026. **Status: LOCKED 8 Nov 2026.** Steve: "sure let's do it." Locks by committing this document
with `study/ovs_peers.py` and its crash results, before the one real run.

---

## Plain-English Summary (For Steve)

**The problem.** An elite player is compared with the 30 past players most like him. But there are only a handful of
true game-breakers at any position, so most of his 30 are merely good players, and they drag his value down. That's the
Bowers, McBride and Gibbs problem.

**The change.** For elite players only, use his **10 closest** past matches instead of 30.

**The test.** For elite players from 2013–2022, does that predict their next three seasons at least 2% better, without
hurting anyone else?

## 1. The Change, And Only The Change

- **Elite** = a veteran in the top 10% of veterans at his position that season by era-adjusted production (all of
  that season's veteran snapshots). Known at the time.
- **Elite players:** value = recency-weighted average (Fix 2, half-life 8) of his **10 closest** matches, the first 10 of
  the same 30 the adopted value uses (same features, same weights).
- **Everyone else, and rookies:** the adopted value (era-adjusted, three seasons ahead, offseason changes;
  `docs/PREREG-ovs-offseason.md`), unchanged.
- **Rows:** 587 elite veteran snapshots (QB 82, RB 165, WR 218, TE 122) among 6,484 test rows, 2013–2022.

## 2. The Questions

- **Decides:** RMSE on FV3 over the 587 elite rows, 10 vs 30 matches: at least **2% better**, paired permutation p < 0.05
  (a player's rows together, 10,000 shuffles); **and** all rows no more than 0.5% worse; **and** close synthetic trades
  no more than 1.0 point worse.
- **Decision:** passes → elite players use their 10 closest matches (Steve's OK). Fails → 30 for everyone.

## 3. Reported, Deciding Nothing

By position among elite players; elite players' produced ÷ predicted both ways (is the 30-match value too low for
them?); today's values for Gibbs, Bowers, McBride, Chase, Bijan.

## 4. Prior Looks

- The adopted value's results on these seasons are known.
- 8 Nov: Gibbs's, Bowers's and Dart's 30 matches were looked at (Gibbs: Tomlinson, Kamara, Peterson; Bowers: Gates,
  Graham, Witten). No 10-match prediction has been compared with any outcome.

## 5. Crash Tests, Before Lock

The era study's worlds with this rule: noise passes in at most 1 of 20; planted w = 0.75 passes in ≥ 80% of 200; w = 0.6
reported.

## 6. Limits

- One cut-off (top 10%) and one size (10), chosen before any result; not tuned.
- Fewer matches means a noisier value; the test is whether closeness beats that.

## 7. Not Licensed Here

The DELTA Score, the site's model value, buy/sell calls. Nothing on the site changes.

## 8. Amendments

**Crash tests (8 Nov, `study/out/ovs_peers_crash.json`): PASS.** Noise world 0 of 20; planted w = 0.75 **192 of 200**
(96%), typical elite lift 7.8%; w = 0.6: 16 of 50.
