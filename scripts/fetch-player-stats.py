#!/usr/bin/env python3
"""
DELTA Player Stats Fetcher
Runs nightly via GitHub Actions alongside fetch-market-values.js

Uses nfl-data-py (wraps nflverse data) to fetch official NFL weekly stats.
Calculates season totals and writes data/player-stats.json with raw stat lines.

Raw stats are stored (not pre-calculated PPG) so the client can calculate
PPG for any scoring format via the dropdown.
"""

import json
import os
import sys
from pathlib import Path

try:
    import nfl_data_py as nfl
    import pandas as pd
except ImportError:
    print("[DELTA] Installing nfl-data-py...")
    os.system("pip install nfl-data-py pandas --quiet")
    import nfl_data_py as nfl
    import pandas as pd

# ── CONFIG ─────────────────────────────────────────────────────────────────
SEASONS      = [2023, 2024, 2025]
OUT_DIR      = Path(__file__).parent.parent / "data"
OUT_FILE     = OUT_DIR / "player-stats.json"
INDEX_HTML   = Path(__file__).parent.parent / "index.html"

# ── LOAD DELTA PLAYER NAMES FROM index.html ────────────────────────────────
def get_delta_players():
    """Extract all player names from RAW array in index.html"""
    import re
    if not INDEX_HTML.exists():
        print("[DELTA] index.html not found — using empty player list")
        return []
    html = INDEX_HTML.read_text(encoding='utf-8')
    raw_start = html.find('const RAW=[')
    raw_end   = html.find('\nconst PICKS=', raw_start)
    raw       = html[raw_start:raw_end]
    names     = re.findall(r"n:'([^']+)'", raw)
    # Filter out rookies with no NFL data
    return [n for n in names if n]

# ── NORMALISE NAME FOR MATCHING ─────────────────────────────────────────────
def norm(name):
    """Normalise player name for fuzzy matching"""
    import re
    return re.sub(r"[^a-z\s']", '', 
           re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?', '',
           name.lower())).strip()

# ── FETCH STATS ─────────────────────────────────────────────────────────────
def fetch_season_stats(seasons):
    """Fetch weekly stats from nflverse and aggregate to season totals"""
    print(f"[DELTA] Fetching weekly stats for seasons: {seasons}")

    # import_weekly_data returns a DataFrame with one row per player per week
    df = nfl.import_weekly_data(
        years=seasons,
        columns=[
            'player_id', 'player_display_name', 'position',
            'season', 'week', 'season_type',
            'completions', 'attempts', 'passing_yards', 'passing_tds', 'interceptions',
            'rushing_yards', 'rushing_tds', 'rushing_fumbles_lost',
            'receptions', 'targets', 'receiving_yards', 'receiving_tds',
        ]
    )

    # Regular season only
    df = df[df['season_type'] == 'REG'].copy()
    print(f"[DELTA] Raw rows: {len(df)}")

    # Aggregate to season totals
    agg = df.groupby(['player_display_name', 'position', 'season']).agg(
        games        = ('week',            'nunique'),
        pass_yds     = ('passing_yards',   'sum'),
        pass_td      = ('passing_tds',     'sum'),
        pass_int     = ('interceptions',   'sum'),
        rush_yds     = ('rushing_yards',   'sum'),
        rush_td      = ('rushing_tds',     'sum'),
        rec          = ('receptions',      'sum'),
        rec_yds      = ('receiving_yards', 'sum'),
        rec_td       = ('receiving_tds',   'sum'),
    ).reset_index()

    print(f"[DELTA] Season aggregations: {len(agg)} player-seasons")
    return agg

# ── MATCH DELTA NAMES TO NFL DATA ───────────────────────────────────────────
def build_stats_map(agg, delta_names):
    """Match DELTA player names to nflverse player names"""
    # Build lookup: normalised_name → display_name (from nflverse)
    nfl_names = agg['player_display_name'].unique()
    nfl_norm  = {norm(n): n for n in nfl_names}

    matched    = {}
    not_found  = []

    for delta_name in delta_names:
        key = norm(delta_name)
        if key in nfl_norm:
            matched[delta_name] = nfl_norm[key]
        else:
            # Try partial match (handles Jr./Sr. suffix differences)
            words   = key.split()
            found   = None
            for length in range(len(words), 1, -1):
                partial = ' '.join(words[:length])
                candidates = [v for k, v in nfl_norm.items() if k.startswith(partial)]
                if len(candidates) == 1:
                    found = candidates[0]
                    break
            if found:
                matched[delta_name] = found
            else:
                not_found.append(delta_name)

    print(f"[DELTA] Matched: {len(matched)}/{len(delta_names)}")
    if not_found:
        print(f"[DELTA] Unmatched ({len(not_found)}): {', '.join(not_found[:20])}")

    return matched

# ── BUILD OUTPUT ─────────────────────────────────────────────────────────────
def build_output(agg, matched, seasons):
    """Build the player-stats.json output structure"""
    players = {}

    for delta_name, nfl_name in matched.items():
        player_data = {}
        player_rows = agg[agg['player_display_name'] == nfl_name]

        for season in seasons:
            season_row = player_rows[player_rows['season'] == season]
            if season_row.empty:
                player_data[season] = None
                continue

            row = season_row.iloc[0]
            g   = int(row['games'])
            if g == 0:
                player_data[season] = None
                continue

            player_data[season] = {
                'games':    g,
                'rec':      round(float(row['rec']),      1),
                'rec_yds':  int(row['rec_yds']),
                'rec_td':   int(row['rec_td']),
                'rush_yds': int(row['rush_yds']),
                'rush_td':  int(row['rush_td']),
                'pass_yds': int(row['pass_yds']),
                'pass_td':  int(row['pass_td']),
                'pass_int': int(row['pass_int']),
            }

        players[delta_name] = player_data

    return players

# ── SPOT CHECK ───────────────────────────────────────────────────────────────
def spot_check(players, season=2025):
    """Calculate PPG for a few known players to verify data"""
    checks = ['Josh Allen', "Ja'Marr Chase", 'Bijan Robinson', 'Trey McBride']
    print(f"\n[DELTA] Spot check ({season}, half PPR + TE premium):")
    for name in checks:
        s = players.get(name, {}).get(season)
        if not s or s['games'] == 0:
            print(f"  {name}: no data")
            continue
        pos = 'QB'  # default; client knows position from RAW
        ppr = 1.0 if name in ['Trey McBride', 'Brock Bowers'] else 0.5
        pts = (s['rec'] * ppr + s['rec_yds'] * 0.1 + s['rec_td'] * 6
             + s['rush_yds'] * 0.1 + s['rush_td'] * 6
             + s['pass_yds'] * 0.04 + s['pass_td'] * 4 - s['pass_int'] * 2)
        ppg = round(pts / s['games'], 1)
        print(f"  {name}: {s['games']}g → {ppg} PPG")

# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    import datetime
    print(f"[DELTA] Player stats fetch starting at {datetime.datetime.utcnow().isoformat()}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Get DELTA player names
    delta_names = get_delta_players()
    print(f"[DELTA] {len(delta_names)} players in DELTA RAW array")

    # 2. Fetch nflverse weekly stats
    agg = fetch_season_stats(SEASONS)

    # 3. Match names
    matched = build_stats_map(agg, delta_names)

    # 4. Build output
    players = build_output(agg, matched, SEASONS)

    # 5. Write file
    output = {
        'fetched':  datetime.datetime.utcnow().isoformat() + 'Z',
        'seasons':  SEASONS,
        'note':     'Raw stats — PPG calculated client-side per scoring format',
        'players':  players,
    }
    OUT_FILE.write_text(json.dumps(output, indent=2))
    kb = len(json.dumps(output)) // 1024
    print(f"\n[DELTA] player-stats.json written ({kb}KB, {len(players)} players)")

    # 6. Spot check
    spot_check(players)

if __name__ == '__main__':
    main()
