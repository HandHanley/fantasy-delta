# Plan — Contract History For Measuring Opportunity Security (9 Nov 2026)

**Steve, 9 Nov:** "I think what we really should be looking at is opportunity, not performance … the not great players
getting long contracts means those players get to be not great for longer." Then: "yeah that sounds good" to building
the free rookie-deal part first and sizing the rest.

## What It Measures

For veterans by contract status (contract year, 1 year left, 2+ years left, plus how much money is committed), against
similar players without that security:

1. **Opportunity kept:** QB starts; snap share and targets for the others.
2. **Points delivered:** what that opportunity turned into over the next three seasons, which is what dynasty value is.

The result is a size with a margin of error, by position where the numbers allow. It is used as a labelled layer, as a
stated exception to the 2% rule: `docs/POWER-contract-bump.md` shows that no layer of this kind can ever pass that rule.

## Step 1 — Done: The Free Part

`study/contract_history.py` → `study/out/contract_history_rookie.csv`, `contract_history_rows.csv`,
`contract_history_job.json`.

- **Rookie deals:** players drafted from 2011 on, entering their second or third season, are certainly on the four-year
  rookie deal, because no extension is allowed before the third season ends. That's DELTA's `rookie_rule`. The source
  for each row is that year's NFL draft page, the same as the current table.
- **Checked:** the rule matches DELTA's own table on all 187 current rookie deals, with no disagreements.
- **Free rows:** 1,385 veteran seasons (569 fantasy-relevant).

## The Remaining Job

Fantasy-relevant means a top QB 36, RB 60, WR 84 or TE 36 by fantasy points that season.

| | Full History (2004–2022) | Recent Only (2013–2022) |
|---|---|---|
| Fantasy-relevant veteran seasons | 4,106 | 2,162 |
| Fifth-year option decisions | 69 players | 69 players |
| Extension checks (end of rookie deal) | 187 players | 187 players |
| Veteran deals from reports | 946 players, about 1,570 deals | 510 players, about 810 deals |
| Margin of error on the bump (90% range) | about ±4 points | about ±6 points |

- **Where the precision comes from:** the "recent only" figure comes from `study/out/ovs_contract_power_relevant_2013_2022.json`,
  which measured the 1,513 relevant rows with three seasons of results by 2022.
- **The lookup list (recent only):** `study/out/contract_lookups_2013_2022.csv`, one row per player per kind of lookup.

## Rules For Every Lookup

- **The source is the original report:** the team's announcement, AP, NFL.com, or the reporter who broke the deal. A
  player's Wikipedia page is a fast index to his deals and the reports it cites. The row records the original report,
  not Wikipedia.
- **Never OverTheCap or Spotrac pages,** even when a search lands there.
- **Recorded the same way as `data/delta-contracts.json`:**
  - fields `end`, `kind`, `aav`, `total`, `basis`, `source`;
  - the same `contract_rule`: the last playable season written into the deal; no void years; the option only once it
    is picked up;
  - plus the signing date, so each snapshot uses only what was known before that season.
- **Kept separate from the live table:** `study/data/contract-history.json`. The live table is today's contracts and the
  site reads it.

## Next

Steve picks the size (full or recent only). Then the lookups run in batches across sessions, starting with the 69
option decisions and 187 extension checks, the quickest and most decisive group.

## The Lookups Are Being Filled By ChatGPT (9 Nov 2026)

Steve is having ChatGPT research `study/out/contract_lookups_2013_2022.csv`. The prompt he was given asks for a **new**
CSV, one row per contract, with exactly these columns:

`Player ID, Player, Position, What To Look Up, Contract Number, Team, Signed Date, Kind, First Season, Last Season,
Years, Total ($M), AAV ($M), Guaranteed At Signing ($M), Option Status, Released Date, Source URL, Source Outlet, Notes,
Confidence`

**What the prompt asked for:**

- **Kind** is one of: rookie, rookie_option, veteran, extension, franchise_tag, transition_tag, rfa_tender,
  practice_squad, none.
- **Dates** are YYYY-MM-DD. **Money** is in $ millions, as reported, blank if not reported.
- **Confidence** is high, medium or low.
- **Seasons:** First Season for an extension is the first new season added. Last Season is the last playable season
  written into the deal: no void years, and the fifth-year option only if exercised (DELTA's `contract_rule`).
- **Sources:** original reports only. Wikipedia is allowed only to find a deal. Never overthecap.com or spotrac.com.
  No invented links: when unsure, Confidence is low.
- **Order:** option rows first, then extension checks, then veteran deals, in batches of about 25 players. Steve sends
  the option and extension rows back first, for a quality check before the rest.

**Checks before anything is used:**

- no overthecap.com or spotrac.com links;
- every input player present;
- dates in order, and First/Last Season consistent with the signing date;
- teams match the season rosters;
- extension First Season after the old deal;
- a hand spot-check of about 20 deals against their sources.

Then store it as `study/data/contract-history.json`, pre-register the measurement (opportunity kept, and points
delivered, by contract status and money committed), and run it.
