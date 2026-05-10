#!/usr/bin/env python3
"""
DELTA Player Stats Fetcher — clean rewrite
Uses nflreadpy to fetch NFL weekly stats from nflverse.
Stores raw stat lines in data/player-stats.json.
"""

import json, os, re, datetime
from pathlib import Path

try:
    import nflreadpy as nfl
    import polars as pl
except ImportError:
    os.system("pip install 'nflreadpy@git+https://github.com/nflverse/nflreadpy' polars pyarrow pandas --quiet")
    import nflreadpy as nfl
    import polars as pl

SEASONS    = [2023, 2024, 2025]
OUT_DIR    = Path(__file__).parent.parent / "data"
OUT_FILE   = OUT_DIR / "player-stats.json"
INDEX_HTML = Path(__file__).parent.parent / "index.html"

def get_delta_players():
    if not INDEX_HTML.exists():
        return []
    html  = INDEX_HTML.read_text(encoding='utf-8')
    start = html.find('const RAW=[')
    end   = html.find('\nconst PICKS=', start)
    return re.findall(r"n:'([^']+)'", html[start:end])

def norm(name):
    """Normalise to lowercase letters/spaces only, strip suffixes and punctuation."""
    import unicodedata
    name = unicodedata.normalize('NFKD', str(name))
    name = re.sub(r"[^a-z0-9\s]", '', name.lower())
    name = re.sub(r'\b(jr|sr|ii|iii|iv)\b', '', name)
    return re.sub(r'\s+', ' ', name).strip()

def fetch_season_stats():
    print(f"[DELTA] Fetching weekly stats for {SEASONS}...")
    df = nfl.load_player_stats(seasons=SEASONS)

    # Convert polars → pandas
    pdf = df.to_pandas() if hasattr(df, 'to_pandas') else df

    # Regular season only
    if 'season_type' in pdf.columns:
        pdf = pdf[pdf['season_type'] == 'REG'].copy()

    print(f"[DELTA] Rows: {len(pdf)}")
    print(f"[DELTA] All columns: {list(pdf.columns)}")

    # Find columns
    def col(*opts):
        return next((o for o in opts if o in pdf.columns), None)

    # Name column — player_display_name has FULL names like "Josh Allen"
    # player_name has abbreviated names like "J.Allen" — DO NOT USE for grouping
    name_col    = col('player_display_name')  # MUST be display name
    season_col  = col('season', 'year')
    week_col    = col('week', 'game_week')
    pos_col     = col('position', 'pos')
    pass_yd_col = col('passing_yards', 'pass_yards')
    pass_td_col = col('passing_tds', 'passing_touchdowns')
    pass_int_col= col('passing_interceptions', 'interceptions', 'pass_int')
    rush_yd_col = col('rushing_yards', 'rush_yards')
    rush_td_col = col('rushing_tds', 'rushing_touchdowns')
    rec_col     = col('receptions', 'rec')
    rec_yd_col  = col('receiving_yards', 'rec_yards')
    rec_td_col  = col('receiving_tds', 'receiving_touchdowns')

    if not name_col:
        raise ValueError(f"No display name column found. Available: {list(pdf.columns)}")

    print(f"[DELTA] Using name col: {name_col}")
    print(f"[DELTA] Sample names: {pdf[name_col].dropna().unique()[:5].tolist()}")

    # Fill nulls
    for c in [pass_yd_col, pass_td_col, pass_int_col, rush_yd_col, rush_td_col,
              rec_col, rec_yd_col, rec_td_col]:
        if c and c in pdf.columns:
            pdf[c] = pdf[c].fillna(0)

    # Build PROPER name lookup from player_name col (has Ja'Marr not Jamarr)
    proper_names = {}  # norm(display_name) → proper_name
    if 'player_name' in pdf.columns:
        for _, row in pdf[[name_col, 'player_name']].drop_duplicates().iterrows():
            dn = str(row[name_col]) if row[name_col] else ''
            pn = str(row['player_name']) if row['player_name'] else ''
            # player_name is abbreviated (J.Allen), not useful for lookup
            # But we want norm(display) → display for consistency
            if dn:
                proper_names[norm(dn)] = dn

    # Aggregate to season totals — group by display name
    group_cols = [c for c in [name_col, season_col, pos_col] if c]

    agg_dict = {'games': (week_col or 'week', 'nunique')}
    for stat_name, col_name in [
        ('pass_yds',  pass_yd_col),  ('pass_td',   pass_td_col),
        ('pass_int',  pass_int_col), ('rush_yds',  rush_yd_col),
        ('rush_td',   rush_td_col),  ('rec',       rec_col),
        ('rec_yds',   rec_yd_col),   ('rec_td',    rec_td_col),
    ]:
        if col_name and col_name in pdf.columns:
            agg_dict[stat_name] = (col_name, 'sum')

    result = pdf.groupby(group_cols).agg(**agg_dict).reset_index()
    result.rename(columns={name_col: 'player_name', season_col: 'season'}, inplace=True)

    print(f"[DELTA] Aggregated: {len(result)} player-seasons")
    print(f"[DELTA] Sample player names after agg: {result['player_name'].unique()[:5].tolist()}")
    return result

def match_names(agg, delta_names):
    nfl_names = agg['player_name'].unique()
    nfl_norm  = {norm(n): n for n in nfl_names}

    print(f"[DELTA] nfl_norm size: {len(nfl_norm)}")
    print(f"[DELTA] Sample nfl_norm keys: {list(nfl_norm.keys())[:5]}")

    # Check if Josh Allen matches
    print(f"[DELTA] 'josh allen' in nfl_norm: {'josh allen' in nfl_norm}")
    if 'josh allen' in nfl_norm:
        print(f"[DELTA] Josh Allen maps to: {nfl_norm['josh allen']}")

    # Known aliases: DELTA name → nflverse display name
    ALIASES = {
        'Chigoziem Okonkwo': 'Chig Okonkwo',
    }

    matched   = {}
    not_found = []

    for name in delta_names:
        # Check alias first
        lookup = ALIASES.get(name, name)
        key    = norm(lookup)

        if key in nfl_norm:
            matched[name] = nfl_norm[key]
        else:
            # Partial match fallback
            words  = key.split()
            found  = None
            for length in range(len(words), 1, -1):
                partial  = ' '.join(words[:length])
                cands    = [v for k, v in nfl_norm.items() if k.startswith(partial)]
                if len(cands) == 1:
                    found = cands[0]
                    break
            if found:
                matched[name] = found
            else:
                not_found.append(name)

    print(f"[DELTA] Matched: {len(matched)}/{len(delta_names)}")
    if not_found:
        unmatched_vets = [n for n in not_found if not any(
            n in x for x in ['Love', 'Tate', 'Tyson', 'Simpson', 'Sadiq', 'Lemon',
                              'Concepcion', 'Cooper', 'Price', 'Boston', 'Bernard',
                              'Stowers', 'Klein', 'Klare', 'Beck', 'Roush', 'Williams',
                              'Delp', 'Fields', 'Branch', 'Brazzell', 'Hurst', 'Allar',
                              'Kacmarek', 'Mendoza', 'Nussmeier', 'Klubnik', 'Burks']
        )]
        if unmatched_vets:
            print(f"[DELTA] Unmatched veterans: {unmatched_vets[:10]}")
        rookies = [n for n in not_found if n not in unmatched_vets]
        print(f"[DELTA] Unmatched rookies (expected): {len(rookies)}")
    return matched

def build_output(agg, matched):
    players = {}
    stat_cols = ['games','pass_yds','pass_td','pass_int',
                 'rush_yds','rush_td','rec','rec_yds','rec_td']

    for delta_name, nfl_name in matched.items():
        rows = agg[agg['player_name'] == nfl_name]
        player_data = {}
        for season in SEASONS:
            srow = rows[rows['season'] == season]
            if srow.empty or int(srow.iloc[0].get('games', 0)) == 0:
                player_data[season] = None
                continue
            r = srow.iloc[0]
            player_data[season] = {
                'games':    int(r.get('games',    0)),
                'rec':      round(float(r.get('rec',      0)), 1),
                'rec_yds':  int(r.get('rec_yds',  0)),
                'rec_td':   int(r.get('rec_td',   0)),
                'rush_yds': int(r.get('rush_yds', 0)),
                'rush_td':  int(r.get('rush_td',  0)),
                'pass_yds': int(r.get('pass_yds', 0)),
                'pass_td':  int(r.get('pass_td',  0)),
                'pass_int': int(r.get('pass_int', 0)),
            }
        players[delta_name] = player_data
    return players

def spot_check(players, season=2025):
    checks = [
        ('Josh Allen',     0.0, 4),
        ("Ja'Marr Chase",  0.5, 4),
        ('Bijan Robinson', 0.5, 4),
        ('Trey McBride',   1.0, 4),
        ('Justin Jefferson',0.5,4),
    ]
    print(f"\n[DELTA] Spot check ({season}, scoring: 4PT pass TD):")
    for name, ppr, pass_td_pts in checks:
        s = players.get(name, {}).get(season)
        if not s or not s.get('games'):
            print(f"  {name}: no data"); continue
        pts = (s['rec']*ppr + s['rec_yds']*0.1 + s['rec_td']*6
             + s['rush_yds']*0.1 + s['rush_td']*6
             + s['pass_yds']*0.04 + s['pass_td']*pass_td_pts - s['pass_int']*2)
        print(f"  {name}: {s['games']}g → {round(pts/s['games'],1)} PPG")

def main():
    print(f"[DELTA] Starting at {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    delta_names = get_delta_players()
    print(f"[DELTA] {len(delta_names)} players in DELTA RAW")

    agg     = fetch_season_stats()
    matched = match_names(agg, delta_names)
    players = build_output(agg, matched)

    output = {
        'fetched': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'seasons': SEASONS,
        'note':    'Raw stats — PPG calculated client-side per scoring format dropdown',
        'players': players,
    }
    OUT_FILE.write_text(json.dumps(output, indent=2))
    kb = len(json.dumps(output)) // 1024
    print(f"[DELTA] player-stats.json written ({kb}KB, {len(players)} players)")
    spot_check(players)

if __name__ == '__main__':
    main()
