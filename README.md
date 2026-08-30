# DELTA

**Dynasty Efficiency & Long-Term Analysis** — a dynasty fantasy football analytics
platform. Live at **[fantasydelta.com](https://fantasydelta.com)**.

DELTA scores every dynasty-relevant NFL player on what they have *demonstrated*,
projects production, and shows where its model disagrees with market prices. It
also tracks college players years before they are draft-eligible, in the same
place, on the same terms.

It is free, ad-free, and needs no account. It is built and maintained by one
person.

---

## What makes it different

**It shows its work.** Every number on the site traces back to the code in this
repository. That is the reason the repo is public.

**It grades itself in public.** DELTA freezes its rankings and projections before
the season, then reconciles them against what actually happened — whether they
hold up or not. The tests are registered in advance so the scoring rules cannot
be moved after the fact.

**It separates what it knows from what it guesses.** Production data is a fact.
A projection is a claim. The interface keeps those apart rather than blending
them into one confident-looking number.

---

## The model, briefly

The DELTA Score is built from four axes, all drawn from the data pipeline and
none from projections:

| Axis | Weight | What it measures |
|---|---|---|
| Age | 15 | Position-specific value curve over a 2–3 year dynasty window |
| Production | 45 | What the player has actually done, competition-adjusted |
| Opportunity | 30 | Role and usage, including draft capital for young players |
| Contract | 10 | Situation and security |

Running backs are scored on a variant of this weighting — production is scaled up
and opportunity down — because for a back, usage and production measure
substantially the same thing and would otherwise be double-counted.

Scores update on a season cadence. They deliberately do **not** swing on small
in-season samples.

Buy/sell verdicts are computed against a fixed 12-team superflex, half-PPR
anchor, so a verdict means something about the player rather than about your
league settings.

**College players are never scored.** The college arm reports production facts —
dominator ratings, usage, efficiency, recruiting pedigree, competition
adjustment — and stops there. Raw college production without competition context
is misleading, and a single-number college ranking would imply a confidence the
data does not support.

---

## Repository layout

```
index.html              The application — all tabs, all views
delta-engine.js         Scoring, projections, market values, the shared data layer
player.html             NFL player card
cfb-player.html         College player card
delta-sync.js           Optional account sync (Supabase); no-ops when signed out
privacy.html
terms.html

scripts/
  fetch-market-values.js        Dynasty market values
  fetch-scarcity-validation.js  Positional scarcity fitting
  fetch-player-stats.py         NFL season stats
  fetch-game-logs.py            NFL game logs
  fetch-college.py              College production, recruiting, portal
  build-college-index.js        College → NFL name index and season list
  engine-audit-gate.js          Blocks a data commit if the engine audit fails

.github/workflows/
  update-market-values.yml      NFL pipeline
  fetch-college.yml             College pipeline
  deploy-pages.yml              Publishes after either data workflow succeeds

data/                   Generated JSON. Not hand-edited. See NOTICE.md.
```

## Pipelines

Both data workflows run on a schedule and commit their output. Because a commit
made with the default token cannot trigger `on: push`, `deploy-pages.yml` watches
for those workflows completing and publishes from there. **Any new workflow that
commits data must be added to that watch list**, or its files will land in the
repo and never reach the site.

The college pipeline has a **probe mode** — a workflow input that reports whether
the upstream source has this week's box scores yet, for one or two API calls,
writing nothing.

## The engine audit

`fantasydelta.com/?dev=1` exposes an Engine Audit tab: a suite of invariant
checks over the live engine. It also runs in CI, where a failure blocks the data
commit. A change that moves the model is expected to move audit results; a change
that should not move the model and does is a bug.

---

## Data sources

Player stats and play-by-play from **nflverse**, college data from
**CollegeFootballData**, dynasty market values from **FantasyCalc**, contracts
from **OverTheCap**, and league data from **Sleeper** at the user's request.

Each source has its own terms, and those terms apply to the files in `data/`
regardless of this repository's licence. **See [NOTICE.md](NOTICE.md) before
forking** — particularly for the FTN charting data, which is share-alike.

## Licence

Source code is licensed under **PolyForm Noncommercial 1.0.0** — see
[LICENSE.md](LICENSE.md). Read it, run it, learn from it, build on it for
noncommercial purposes. Do not resell it.

`data/` is not covered by that licence and is not DELTA's to sublicense.
See [NOTICE.md](NOTICE.md).

---

DELTA is an independent project, not affiliated with, endorsed by, or sponsored
by the NFL, the NFLPA, Sleeper, or any data provider named above.

Issues and pull requests are not actively monitored — this is a personal project
maintained around a full-time job.
