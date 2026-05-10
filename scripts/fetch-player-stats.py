#!/usr/bin/env python3
"""
DELTA Player Stats Fetcher
Uses nflreadpy (official nflreadr Python port) to fetch NFL weekly stats.
Stores raw stat lines in data/player-stats.json so the client can calculate
PPG for any scoring format via the dropdown.
"""

import json, os, re, datetime
from pathlib import Path

# ── INSTALL DEPS ──────────────────────────────────────────────────────────
try:
    import nflreadpy as nfl
    import polars as pl
except ImportError:
    print("[DELTA] Installing nflreadpy...")
    os.system("pip install 'nflreadpy@git+https://github.com/nflverse/nflreadpy' polars --quiet")
    import nflreadpy as nfl
    import polars as pl

# ── CONFIG ────────────────────────────────────────────────────────────────
SEASONS    = [2023, 2024, 2025]
OUT_DIR    = Path(__file__).parent.parent / "data"
OUT_FILE   = OUT_DIR / "player-stats.json"
INDEX_HTML = Path(__file__).parent.parent / "index.html"

# ── LOAD DELTA PLAYER NAMES ───────────────────────────────────────────────
def get_delta_players():
    if not INDEX_HTML.exists():
        print("[DELTA] index.html not found")
        return []
    html  = INDEX_HTML.read_text(encoding='utf-8')
    start = html.find('const RAW=[')
    end   = html.find('\nconst PICKS=', start)
    raw   = html[start:end]
    return re.findall(r"n:'([^']+)'", raw)

# ── NORMALISE NAME ────────────────────────────────────────────────────────
def norm(name):
    # Strip ALL quote/apostrophe variants — nflverse omits them
    import unicodedata
    # Normalize unicode (converts curly quotes to ASCII equivalents)
    name = unicodedata.normalize('NFKD', name)
    # Remove ALL non-alphanumeric except spaces
    name = re.sub(r"[^a-z0-9\s]", '', name.lower())
    # Remove suffixes
    name = re.sub(r'\b(jr|sr|ii|iii|iv)\b', '', name)
    return re.sub(r'\s+', ' ', name).strip()

# ── FETCH & AGGREGATE ─────────────────────────────────────────────────────
def fetch_season_stats():
    print(f"[DELTA] Fetching player stats for seasons {SEASONS}...")
    # load_player_stats returns weekly player stats
    df = nfl.load_player_stats(seasons=SEASONS)

    # Convert to pandas for easier aggregation
    pdf = df.to_pandas() if hasattr(df, 'to_pandas') else df

    # Regular season only
    if 'season_type' in pdf.columns:
        pdf = pdf[pdf['season_type'] == 'REG']

    print(f"[DELTA] Rows fetched: {len(pdf)}")
    print(f"[DELTA] Columns: {list(pdf.columns[:20])}")

    # Identify column names (nflverse uses different names across versions)
    col = lambda *opts: next((o for o in opts if o in pdf.columns), None)

    name_col    = col('player_display_name', 'player_name', 'full_name')
    pos_col     = col('position', 'pos')
    season_col  = col('season', 'year')
    week_col    = col('week', 'game_week')
    pass_yd_col = col('passing_yards', 'pass_yards', 'pass_yds')
    pass_td_col = col('passing_tds', 'pass_tds', 'passing_touchdowns')
    pass_int_col= col('interceptions', 'int', 'pass_int')
    rush_yd_col = col('rushing_yards', 'rush_yards', 'rush_yds')
    rush_td_col = col('rushing_tds', 'rush_tds', 'rushing_touchdowns')
    rec_col     = col('receptions', 'rec')
    rec_yd_col  = col('receiving_yards', 'rec_yards', 'rec_yds')
    rec_td_col  = col('receiving_tds', 'rec_tds', 'receiving_touchdowns')

    print(f"[DELTA] Key columns found: name={name_col} pos={pos_col} pass_yds={pass_yd_col} rec={rec_col}")

    if not name_col:
        raise ValueError("Could not find player name column")

    # Fill missing columns with 0
    for c in [pass_yd_col, pass_td_col, pass_int_col, rush_yd_col, rush_td_col,
              rec_col, rec_yd_col, rec_td_col]:
        if c and c in pdf.columns:
            pdf[c] = pdf[c].fillna(0)

    # Aggregate to season totals
    agg_cols = {
        'games':    (week_col or 'week', 'nunique'),
    }
    numeric = {
        'pass_yds':  pass_yd_col,
        'pass_td':   pass_td_col,
        'pass_int':  pass_int_col,
        'rush_yds':  rush_yd_col,
        'rush_td':   rush_td_col,
        'rec':       rec_col,
        'rec_yds':   rec_yd_col,
        'rec_td':    rec_td_col,
    }

    group_cols = [name_col, season_col]
    if pos_col: group_cols.append(pos_col)

    grouped = pdf.groupby(group_cols)

    result = grouped.agg(
        games=(week_col or 'week', 'nunique'),
        **{k: (v, 'sum') for k, v in numeric.items() if v and v in pdf.columns}
    ).reset_index()

    result.rename(columns={name_col: 'player_name', season_col: 'season'}, inplace=True)
    print(f"[DELTA] Aggregated: {len(result)} player-seasons")
    return result

# ── MATCH NAMES ───────────────────────────────────────────────────────────
def match_names(agg, delta_names):
    nfl_names = agg['player_name'].unique()
    nfl_norm  = {norm(n): n for n in nfl_names}

    matched   = {}
    not_found = []

    for name in delta_names:
        key = norm(name)
        if key in nfl_norm:
            matched[name] = nfl_norm[key]
        else:
            words = key.split()
            found = None
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
        print(f"[DELTA] Unmatched: {', '.join(not_found[:25])}")
    return matched

# ── BUILD OUTPUT ──────────────────────────────────────────────────────────
def build_output(agg, matched):
    stat_cols = ['games','pass_yds','pass_td','pass_int',
                 'rush_yds','rush_td','rec','rec_yds','rec_td']
    players   = {}

    for delta_name, nfl_name in matched.items():
        rows = agg[agg['player_name'] == nfl_name]
        player_data = {}
        for season in SEASONS:
            srow = rows[rows['season'] == season]
            if srow.empty:
                player_data[season] = None
                continue
            r = srow.iloc[0]
            g = int(r.get('games', 0))
            if g == 0:
                player_data[season] = None
                continue
            player_data[season] = {
                'games':    g,
                'rec':      round(float(r.get('rec', 0)), 1),
                'rec_yds':  int(r.get('rec_yds', 0)),
                'rec_td':   int(r.get('rec_td', 0)),
                'rush_yds': int(r.get('rush_yds', 0)),
                'rush_td':  int(r.get('rush_td', 0)),
                'pass_yds': int(r.get('pass_yds', 0)),
                'pass_td':  int(r.get('pass_td', 0)),
                'pass_int': int(r.get('pass_int', 0)),
            }
        players[delta_name] = player_data

    return players

# ── SPOT CHECK ────────────────────────────────────────────────────────────
def spot_check(players, season=2025):
    checks = [
        ('Josh Allen',    'QB', 0.0, 4),
        ('JaMarr Chase',  'WR', 0.5, 4),
        ("Ja'Marr Chase", 'WR', 0.5, 4),
        ('Bijan Robinson','RB', 0.5, 4),
        ('Trey McBride',  'TE', 1.0, 4),
        ('Justin Jefferson','WR',0.5, 4),
    ]
    print(f"\n[DELTA] Spot check ({season}):")
    for name, pos, ppr, pass_td_pts in checks:
        s = players.get(name, {}).get(season)
        if not s or not s.get('games'):
            print(f"  {name}: no data"); continue
        pts = (s['rec'] * ppr + s['rec_yds'] * 0.1 + s['rec_td'] * 6
             + s['rush_yds'] * 0.1 + s['rush_td'] * 6
             + s['pass_yds'] * 0.04 + s['pass_td'] * pass_td_pts
             - s['pass_int'] * 2)
        ppg = round(pts / s['games'], 1)
        print(f"  {name}: {s['games']}g → {ppg} PPG")

# ── MAIN ──────────────────────────────────────────────────────────────────
def main():
    print(f"[DELTA] Starting at {datetime.datetime.utcnow().isoformat()}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    delta_names = get_delta_players()
    print(f"[DELTA] {len(delta_names)} players in DELTA RAW")

    agg     = fetch_season_stats()
    matched = match_names(agg, delta_names)
    players = build_output(agg, matched)

    output = {
        'fetched': datetime.datetime.utcnow().isoformat() + 'Z',
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
