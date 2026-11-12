# PRE-REGISTRATION — Can College Production Price A Rookie Class Before The NFL Draft?

**Drafted:** 12 November 2026. **Status: DRAFT, NOT LOCKED.** Steve, 12 Nov: "I am interested in that college test as
well. My assumption is that it will fail, but in the off chance it doesn't, I'd be super interested to know."

---

## Plain-English Summary (For Steve)

**The question.** Before the NFL draft, can a rookie class's college production tell us whether its fantasy picks
will be worth more or less than usual?

**The test.** For each class, measure the college production of the players drafters took in each pick group (the 1st
round's top four, and so on) in their final college season, against the same pick groups in other classes. Then check
whether stronger-than-usual groups went on to produce more than the pick's usual value over their first three NFL
seasons.

**Why it will probably fail, stated now.** There are only about ten classes with three finished NFL seasons. Ten is very
few data points, so the crash test will probably say the test can't see a real effect. If it does, it comes back to you
before any real run.

**First, a data gap.** DELTA's college data starts with the 2020 season, which covers only three testable classes
(2021–2023). The test needs college seasons back to 2013. The site already pulls from CollegeFootballData with your key
(credited), so a one-off backfill job can fetch 2013–2019 the same way. That's a new pull from an approved source, and
it needs your OK.

## 1. Data

- **College:** CollegeFootballData, final college season for each drafted rookie, 2013–2022 seasons (classes
  2014–2023). Backfilled by the existing workflow (`backfill-college-ppa.yml` pattern) with Steve's OK.
- **Measures:** DELTA's existing college numbers, computed the same way as the site's college card:
  - share of team production (dominator; for RBs, rushing and receiving, as `PREREG-rb-dominator-weight.md`);
  - per-play value (PPA);
  - percentiles within position and season.
- **Picks and outcomes:** exactly `PLAN-pick-values-now.md` Stage 1: the superflex rookie-draft order, FV3 over the
  first three seasons, full PPR, the measured lines.

## 2. The Class-Strength Number

For pick group g (Early / Mid / Late of each round) in class c: the average college percentile of the players drafters
took there, minus that group's average over the other classes. That's positive for a stronger-than-usual group. No NFL
data is used.

## 3. The Test

- **Prediction without college:** the pick's Stage 1 value (other classes only).
- **Prediction with college:** Stage 1 × (1 + β × class strength), with β fitted on the other classes (leave one class
  out).
- **Decides:** typical miss over all 360 picks, at least 2% better, with permutation p < 0.05 (a class's picks shuffled
  together).
- **Passes →** pre-draft pick values use class strength (Steve's OK). **Fails →** no change.

## 4. Crash Tests, Before Lock

- **Noise:** college numbers shuffled between classes. It may pass at most 1 of 20.
- **Planted:** an effect of plausible size built in (β set so a one-standard-deviation stronger group produces 25%
  more). It must pass at least 80% of 200.
- **If the planted world fails,** it goes to Steve. That's the expected outcome with ten classes.

## 5. Prior Looks

None. No college number has been compared with any pick outcome.

## 6. Not Licensed Here

- **Player values for drafted rookies:** college numbers stay context only there.
- **The DELTA Score.**
