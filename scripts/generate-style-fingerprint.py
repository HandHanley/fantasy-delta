#!/usr/bin/env python3
"""
Generate PC_FINGERPRINT (the displayed playcaller tendency block) from
data/style-rates.json + playcallers.csv, with:
  • recency weighting  — recent seasons count more (config below)
  • coach carry-forward — a coach's prior-team history follows him to a new job
    (consistent with the validated playcaller-portability finding, alpha ~= 0.5)

Since 7 Oct 2026 it runs in the nightly workflow and writes data/pc-fingerprint.json,
which player.html loads over the PC_FINGERPRINT copy baked into delta-engine.js (kept
as the fallback). It is a DISPLAY artifact only — nothing here feeds the projection
(STYLE_2025 terciles do that), so regenerating it carries no ship-gate, just an eye-test.

THE SEASON IN PROGRESS (owner, 7 Oct 2026) counts BY PLAYS RUN: weight = plays so far /
a typical full season's plays (the 2025 median), so four games counts like about a
quarter of a season and grows each week. A first-year playcaller's chart blends his own
plays with the team's last completed season, the inherited share shrinking as his grows.
Check: with no in-progress file, the output reproduces the 5 Jul table exactly (verified
7 Oct, apart from the JAC/JAX fix below).
"""
import json, csv, sys
from collections import defaultdict

# ── CONFIG: recency weights by season — retune in ONE place ──────────────
SEASON_WEIGHTS   = {2025: 1.0, 2024: 0.9, 2023: 0.5, 2022: 0.25}
CURRENT_SEASON   = 2026                      # whose primary playcallers = "current" coaches
STYLE_JSON       = "data/style-rates.json"
LIVE_JSON        = "data/style-rates-2026.json"   # season in progress; optional
PLAYCALLERS_CSV  = "playcallers.csv"
OUT_JSON         = "data/pc-fingerprint.json"
# Offseason roll: when 2026 completes, move it into STYLE_JSON / SEASON_WEIGHTS, bump
# CURRENT_SEASON and point LIVE_JSON at the new season.

# style-rates.json may code the Rams as 'LA' (current, from nflverse pbp) or
# 'LAR' (after the fetch-style-rates.py normalization fix). Try the natural key
# first, then the alias, so this works against either version of the file.
# Jacksonville: playcallers.csv writes JAC, nflverse writes JAX. Missing until 7 Oct
# 2026, which silently dropped every Jacksonville season (Coen 2025, Taylor 2023-24).
TEAM_ALIAS = {"LAR": "LA", "LA": "LAR", "JAC": "JAX", "JAX": "JAC"}
def skey(season, team, style):
    k = f"{season}|{team}"
    if k in style:
        return k
    alt = TEAM_ALIAS.get(team)
    if alt and f"{season}|{alt}" in style:
        return f"{season}|{alt}"
    return k

# fingerprint d-key -> style-rates.json field. All 8 map directly.
FIELD_MAP = {
    "moti": "motion_pct", "pa_p": "pa_pct", "proe": "proe", "pass": "pass_rate",
    "two_": "two_back_pct", "te2": "te2_snap_proxy", "play": "plays_pg", "adot": "adot",
}

def load_style(path):
    d = json.load(open(path))
    return d.get("teams", d)                 # {"2022|DET": {...}, ...}

def load_playcallers(path):
    coach_hist = defaultdict(dict)           # coach -> {season: team}  (primary only)
    current    = {}                          # team  -> coach           (CURRENT_SEASON)
    with open(path) as f:
        for r in csv.DictReader(f):
            if str(r["is_primary"]).strip().lower() != "true":
                continue
            season, team, coach = int(r["season"]), r["team"], r["playcaller"].strip()
            if season in SEASON_WEIGHTS:
                coach_hist[coach][season] = team    # last primary row per season wins
            if season == CURRENT_SEASON:
                current[team] = coach
    return coach_hist, current

def contribs_for(coach, team, coach_hist, style, live=None, live_w=0.0):
    """Return [(season, weight, team_season_dict)] for a coach, carry-forward across teams.
    `live` is the current team's in-progress season, counted at `live_w` (plays share)."""
    rows = []
    for season, hist_team in coach_hist.get(coach, {}).items():
        key = skey(season, hist_team, style)
        if key in style:
            rows.append((season, SEASON_WEIGHTS[season], style[key]))
    if live and live_w > 0:
        if rows:
            return rows + [(CURRENT_SEASON, live_w, live)], False
        # first-year playcaller: his own plays, blended with the inherited offense
        inherit = []
        for s in sorted(SEASON_WEIGHTS, reverse=True):
            key = skey(s, team, style)
            if key in style:
                if live_w < 1:
                    inherit = [(s, 1.0 - live_w, style[key])]
                break
        return [(CURRENT_SEASON, live_w, live)] + inherit, False
    if rows:
        return rows, False                   # personal history found
    # new coach, no FTN-era play-calling history -> fall back to the team's most
    # recent available season (the offense being inherited). Flag it.
    for s in sorted(SEASON_WEIGHTS, reverse=True):
        key = skey(s, team, style)
        if key in style:
            return [(s, 1.0, style[key])], True
    return [], True

def load_live(path, style):
    """In-progress season by team, and each team's plays share of a full season."""
    import os
    if not os.path.exists(path):
        return {}, {}, None
    live = load_style(path)
    full = sorted(v["plays"] for k, v in style.items()
                  if k.startswith(f"{max(SEASON_WEIGHTS)}|") and v.get("plays"))
    full_plays = full[len(full) // 2] if full else None
    by_team, weight = {}, {}
    for k, v in live.items():
        season, team = k.split("|")
        if int(season) != CURRENT_SEASON or not full_plays or not v.get("plays"):
            continue
        by_team[team] = v
        weight[team] = round(min(1.0, v["plays"] / full_plays), 3)
    return by_team, weight, full_plays

def live_for(team, by_team, weight):
    for t in (team, TEAM_ALIAS.get(team)):
        if t and t in by_team:
            return by_team[t], weight[t]
    return None, 0.0

def main():
    style = load_style(STYLE_JSON)
    coach_hist, current = load_playcallers(PLAYCALLERS_CSV)
    live_by_team, live_weight, full_plays = load_live(LIVE_JSON, style)

    out, fallbacks, live_used = {}, [], {}
    for team, coach in current.items():
        live, lw = live_for(team, live_by_team, live_weight)
        rows, is_fallback = contribs_for(coach, team, coach_hist, style, live, lw)
        if not rows:
            continue
        if live is not None and lw > 0:
            live_used[team] = lw
        used = sorted({s for s, _, _ in rows})
        d = {}
        for dk, sf in FIELD_MAP.items():
            num = den = 0.0
            for _, w, ts in rows:
                v = ts.get(sf)
                if v is None:
                    continue
                num += w * v; den += w
            d[dk] = round(num / den, 1) if den else None
        own = [s for s in used if s == CURRENT_SEASON or coach_hist.get(coach, {}).get(s)]
        out[team] = {"pc": coach, "yrs": (len(own) if not is_fallback else 0), "d": d}
        if is_fallback:
            fallbacks.append((team, coach, used[0] if used else None))

    # percentiles p (0-100) across teams, per metric. Higher value -> higher p
    # for every metric (matches the baked convention: McDaniel motion=100, NYJ=0).
    for dk in FIELD_MAP:
        pairs = sorted(((t, out[t]["d"][dk]) for t in out if out[t]["d"].get(dk) is not None),
                       key=lambda x: x[1])
        n = len(pairs)
        for rank, (t, v) in enumerate(pairs):
            out[t]["d"][dk] = {"v": v, "p": round(100 * rank / (n - 1)) if n > 1 else 50}

    if len(out) < 28:
        sys.exit(f"[gen] only {len(out)} teams — not writing {OUT_JSON}")
    import datetime
    payload = {
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "weights": {str(k): v for k, v in SEASON_WEIGHTS.items()},
        "live_season": CURRENT_SEASON, "live_full_season_plays": full_plays,
        "live_weight": live_used,
        "teams": out,
    }
    with open(OUT_JSON, "w") as f:
        json.dump(payload, f, separators=(",", ":"))

    print(f"[gen] wrote {OUT_JSON} — teams: {len(out)}  weights: {SEASON_WEIGHTS}")
    if live_used:
        lw = sorted(live_used.values())
        print(f"[gen] {CURRENT_SEASON} in progress: {len(live_used)} teams, plays share "
              f"{lw[0]:.2f}–{lw[-1]:.2f} of a {full_plays}-play season")
    if fallbacks:
        print(f"[gen] {len(fallbacks)} new coach(es) with no FTN-era history -> team most-recent-season fallback (yrs=0):")
        for t, c, s in fallbacks:
            print(f"        {t}: {c}  (used {s}|{t})")
    return out

if __name__ == "__main__":
    main()
