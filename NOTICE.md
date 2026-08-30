# Licensing notice

Required Notice: Copyright 2026 DELTA (https://fantasydelta.com)

## What this repository is licensed under

The **source code** in this repository — the engine, the site, and the pipeline
scripts under `scripts/` and `.github/workflows/` — is licensed under the
**PolyForm Noncommercial License 1.0.0**. See [LICENSE.md](LICENSE.md).

In plain terms: you may read it, run it, learn from it, fork it, and build on it
for any noncommercial purpose. You may not use it, or works based on it, in a
commercial product or service.

This repository is public on purpose. Every figure DELTA publishes can be traced
to the code that produced it, and that only works if the code is readable.
Readable is not the same as free to resell.

## What this repository is NOT licensed under

The files under `data/` are **not** DELTA's to license. They are built from
third-party sources, each with its own terms, and those terms travel with the
data regardless of anything in LICENSE.md:

- **nflverse** (via `nflreadpy`) — player stats and play-by-play, CC-BY 4.0.
  Attribution required.
- **FTN charting data** (via nflverse play-by-play) — **CC-BY-SA 4.0**.
  Attribution required, and share-alike terms may extend to derivative works.
  This is the strictest licence in the pipeline; treat anything derived from the
  offense style factors as carrying it.
- **CollegeFootballData** — college production, recruiting and portal data.
  Commercial use permitted at every tier; attribution strongly encouraged.
- **FantasyCalc** — dynasty market values. No published terms; used as an
  undocumented public endpoint.
- **OverTheCap** — contract data.
- **Sleeper** — league and roster data, read-only, fetched in the user's browser
  at their request. Nothing is stored beyond league and roster identifiers.

If you fork this repository, you are responsible for complying with those
sources' terms yourself. DELTA cannot and does not sublicense them to you.

## Trademarks

"DELTA" as used for this project, and the fantasydelta.com name, are not covered
by the code licence. A fork must not present itself as DELTA.

DELTA is an independent project. It is not affiliated with, endorsed by, or
sponsored by the National Football League, the NFL Players Association, Sleeper,
or any data provider named above.

## Questions

Commercial licensing enquiries: through https://fantasydelta.com
