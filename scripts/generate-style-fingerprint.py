#!/usr/bin/env python3
"""
Generate PC_FINGERPRINT (the displayed playcaller tendency block) from
data/style-rates.json + playcallers.csv, with:
  • recency weighting  — recent seasons count more (config below)
  • coach carry-forward — a coach's prior-team history follows him to a new job
    (consistent with the validated playcaller-portability finding, alpha ~= 0.5)

This REPLACES the hand-baked PC_FINGERPRINT const in delta-engine.js. It is a
DISPLAY artifact only — nothing here feeds the projection (STYLE_2025 terciles do
that), so regenerating it carries no ship-gate, just an eye-test.
"""
import json, csv, sys
from collections import defaultdict

# ── CONFIG: recency weights by season — retune in ONE place ──────────────
SEASON_WEIGHTS   = {2025: 1.0, 2024: 0.9, 2023: 0.5, 2022: 0.25}
CURRENT_SEASON   = 2026                      # whose primary playcallers = "current" coaches
STYLE_JSON       = "data/style-rates.json"
PLAYCALLERS_CSV  = "playcallers.csv"

# style-rates.json may code the Rams as 'LA' (current, from nflverse pbp) or
# 'LAR' (after the fetch-style-rates.py normalization fix). Try the natural key
# first, then the alias, so this works against either version of the file.
TEAM_ALIAS = {"LAR": "LA", "LA": "LAR"}
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

def contribs_for(coach, team, coach_hist, style):
    """Return [(season, weight, team_season_dict)] for a coach, carry-forward across teams."""
    rows = []
    for season, hist_team in coach_hist.get(coach, {}).items():
        key = skey(season, hist_team, style)
        if key in style:
            rows.append((season, SEASON_WEIGHTS[season], style[key]))
    if rows:
        return rows, False                   # personal history found
    # new coach, no FTN-era play-calling history -> fall back to the team's most
    # recent available season (the offense being inherited). Flag it.
    for s in sorted(SEASON_WEIGHTS, reverse=True):
        key = skey(s, team, style)
        if key in style:
            return [(s, 1.0, style[key])], True
    return [], True

def main():
    style = load_style(STYLE_JSON)
    coach_hist, current = load_playcallers(PLAYCALLERS_CSV)

    out, fallbacks = {}, []
    for team, coach in current.items():
        rows, is_fallback = contribs_for(coach, team, coach_hist, style)
        if not rows:
            continue
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
        out[team] = {"pc": coach, "yrs": (len(used) if not is_fallback else 0), "d": d}
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

    # emit drop-in JS const
    js = "const PC_FINGERPRINT=" + json.dumps(out, separators=(",", ":")) + ";"
    open("PC_FINGERPRINT.generated.js", "w").write(js)
    json.dump(out, open("PC_FINGERPRINT.generated.json", "w"), indent=2)

    print(f"[gen] teams: {len(out)}  weights: {SEASON_WEIGHTS}")
    if fallbacks:
        print(f"[gen] {len(fallbacks)} new coach(es) with no FTN-era history -> team most-recent-season fallback (yrs=0):")
        for t, c, s in fallbacks:
            print(f"        {t}: {c}  (used {s}|{t})")
    return out

if __name__ == "__main__":
    main()
