# PRE-REGISTRATION — Own Value Scale: The Second-Contract Moment

**Drafted:** 8 November 2026. **Status: DRAFT, NOT LOCKED.** Steve: "do the measurement on B and see if it's worth adding
in" (contracts), then "Yeah let's do both." Locks by committing this document with `study/ovs_second_contract.py` and
its crash results, before the one real run.

---

## Plain-English Summary (For Steve)

**The question.** When a player's rookie deal ends, his team either keeps him (extension, re-signing or tag), he goes
elsewhere, or nobody signs him. The market reacts to that; think of a Rashee Rice extension. Does our value need to
react too, or do his comparables already price it in?

**Where the data comes from.** Public rosters and draft records (nflverse): which club drafted him, and where he is when
the next season starts. No OverTheCap data, whose terms ban use for player valuations.

**The method.** History is the guide. Past players at the same moment are split by what their team did. For each group
we measure how much better or worse than their comparables they went on to do, using only seasons whose three-year
results were already in. That measured ratio scales his value.

**The test.** On end-of-rookie-deal players from 2013–2022, does the scaled value predict their next three seasons at
least 2% better?

## 1. The Change, And Only The Change

- **Base:** the adopted preseason value, meaning era-adjusted matching, three seasons ahead, offseason features, with games
  out of matching (`docs/DECISION-no-games-in-matching.md`).
- **End of rookie deal:** a drafted QB/RB/WR/TE (nflverse `draft_picks`) at his veteran snapshot in season t = draft
  year + 3, the last of the four guaranteed years. First-round option years are not split out, so an exercised option
  counts as "kept". Undrafted players are excluded.
- **Groups (entering season t + 1):**
  - *kept:* his club in the first five weeks of t + 1 (the offseason study's rule) is his club in the season-t roster
    file.
  - *moved:* he is on another club.
  - *none:* he is on no club in those five weeks.
  - Relocated clubs count as the same club (Raiders, Chargers, Rams).
- **Scaling:** value × (sum of outcomes ÷ sum of base values) over his group's end-of-deal rows from seasons ≤ t − 3, all
  positions together. A group with fewer than **30** such rows is not scaled. Nobody else changes.
- **Rows:** 465 end-of-deal test rows (kept 207, moved 172, none 86; QB 59, RB 136, WR 173, TE 97) among 6,484. History:
  730 end-of-deal rows, 2004–2019.

**Checked by hand before any outcome was read:**

| Player | Snapshot Season | Group | What Happened |
|---|---|---|---|
| Mike Evans | 2017 | kept | Extended |
| Davante Adams | 2017 | kept | Extended |
| Le'Veon Bell | 2016 | kept | Franchise tag |
| Todd Gurley | 2018 | kept | Extended |
| Jarvis Landry | 2017 | moved | Traded to Cleveland |
| Brandin Cooks | 2017 | moved | Traded to the Rams |
| Sammy Watkins | 2017 | moved | Signed with Kansas City |
| Kenyan Drake | 2019 | kept | Traded to Arizona mid-season, then tagged there |

## 2. The Questions

- **Decides:** RMSE on FV3 over the 465 end-of-deal rows, scaled vs base. It must be at least **2% better**, with paired
  permutation p < 0.05 (a player's rows together, 10,000 shuffles); **and** all rows no more than 0.5% worse; **and**
  close synthetic trades no more than 1.0 point worse.
- **Decision:** passes → end-of-deal values are scaled by their group's history (Steve's OK). Fails → no
  contract-moment adjustment.

## 3. Reported, Deciding Nothing

- The ratios used, by season and group. This is the measured size of the effect, which is what Steve asked for.
- What each group produced ÷ its base value.

## 4. Prior Looks

- None of these ratios, and no group's produced-vs-value, has been computed.
- The base value's overall results are known (`DECISION-no-games-in-matching.md` §4).

## 5. Crash Tests, Before Lock

The era study's worlds, recomputed for this method:

- **Noise:** outcomes shuffled within position and season, with the ratios re-learned from the shuffled outcomes. It
  may pass in at most 1 of 20.
- **Planted:** w = 0.75 must pass in ≥ 80% of 200; w = 0.6 is reported.

If the planted world fails, the test is too small to see an effect of this size. That goes to Steve before any real run.

## 6. Limits

- **This covers only the end of the rookie deal**, not deal length or money. Veteran contracts need a history built from
  original reports, which is worth doing only if this moment shows an effect.
- **"Kept" mixes long extensions, one-year tags and option years.**
- **The test is small (465 rows).**

## 7. Not Licensed Here

The DELTA Score, the site's model value, buy/sell calls. Nothing on the site changes.

## 8. Amendments

(None yet.)
