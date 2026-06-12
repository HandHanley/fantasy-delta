#!/usr/bin/env python3
"""
DELTA Player Stats Fetcher — clean rewrite
Uses nflreadpy to fetch NFL weekly stats from nflverse.
Stores raw stat lines in data/player-stats.json.
"""

import json, os, re
from datetime import datetime, timezone
from pathlib import Path

try:
    import nflreadpy as nfl
    import polars as pl
    import pandas as pd
except ImportError:
    os.system("pip install 'nflreadpy@git+https://github.com/nflverse/nflreadpy' polars pyarrow pandas --quiet")
    import nflreadpy as nfl
    import polars as pl
    import pandas as pd

SEASONS    = [2023, 2024, 2025]
OUT_DIR    = Path(__file__).parent.parent / "data"
OUT_FILE   = OUT_DIR / "player-stats.json"
INDEX_HTML = Path(__file__).parent.parent / "index.html"

def get_delta_players():
    if not INDEX_HTML.exists():
        return [], set()
    html  = INDEX_HTML.read_text(encoding='utf-8')
    start = html.find('const RAW=[')
    end   = html.find('\nconst PICKS=', start)
    block = html[start:end]
    # Match single-quoted names (most players) and double-quoted names (apostrophe players)
    # Single-quoted: n:'Player Name'
    single = re.findall(r"n:'([^']+)'", block)
    # Double-quoted: n:"Ja'Marr Chase"
    double = re.findall(r'n:"([^"]+)"', block)
    names = single + double
    # Players with g25:0 have no 2025 NFL data — skip during matching
    no_data = set()
    for m in re.finditer(r"n:'([^']+)'[^}]*?,g25:(\d+)", block):
        if m.group(2) == '0':
            no_data.add(m.group(1))
    for m in re.finditer(r'n:"([^"]+)"[^}]*?,g25:(\d+)', block):
        if m.group(2) == '0':
            no_data.add(m.group(1))
    return names, no_data

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
    rush_yd_col      = col('rushing_yards', 'rush_yards')
    rush_td_col      = col('rushing_tds', 'rushing_touchdowns')
    rush_att_col     = col('carries', 'rushing_attempts', 'rush_attempts')
    rec_col          = col('receptions', 'rec')
    rec_yd_col       = col('receiving_yards', 'rec_yards')
    rec_td_col       = col('receiving_tds', 'receiving_touchdowns')
    tgt_col          = col('targets')
    tgt_share_col    = col('target_share')
    air_yds_col      = col('receiving_air_yards', 'air_yards')
    air_yds_share_col= col('air_yards_share')
    team_col         = col('team', 'recent_team', 'posteam')

    if not name_col:
        raise ValueError(f"No display name column found. Available: {list(pdf.columns)}")

    print(f"[DELTA] Using name col: {name_col}")
    print(f"[DELTA] Sample names: {pdf[name_col].dropna().unique()[:5].tolist()}")
    print(f"[DELTA] Opportunity cols — targets:{tgt_col}, tgt_share:{tgt_share_col}, "
          f"air_yds_share:{air_yds_share_col}, carries:{rush_att_col}")

    # Fill nulls
    for c in [pass_yd_col, pass_td_col, pass_int_col, rush_yd_col, rush_td_col,
              rush_att_col, rec_col, rec_yd_col, rec_td_col,
              tgt_col, tgt_share_col, air_yds_col, air_yds_share_col]:
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
    group_cols = [c for c in [name_col, season_col, pos_col, team_col] if c]

    agg_dict = {'games': (week_col or 'week', 'nunique'),
                '_last_week': (week_col or 'week', 'max')}
    for stat_name, col_name in [
        ('pass_yds',       pass_yd_col),   ('pass_td',        pass_td_col),
        ('pass_int',       pass_int_col),  ('rush_yds',       rush_yd_col),
        ('rush_td',        rush_td_col),   ('rush_att',       rush_att_col),
        ('rec',            rec_col),       ('rec_yds',        rec_yd_col),
        ('rec_td',         rec_td_col),    ('targets',        tgt_col),
        ('air_yds',        air_yds_col),
    ]:
        if col_name and col_name in pdf.columns:
            agg_dict[stat_name] = (col_name, 'sum')

    # target_share and air_yards_share are per-week fractions — average them, not sum
    for stat_name, col_name in [
        ('target_share',   tgt_share_col),
        ('air_yds_share',  air_yds_share_col),
    ]:
        if col_name and col_name in pdf.columns:
            agg_dict[stat_name] = (col_name, 'mean')

    result = pdf.groupby(group_cols).agg(**agg_dict).reset_index()
    result.rename(columns={name_col: 'player_name', season_col: 'season'}, inplace=True)

    # Compute rush_share from weekly pdf (pre-aggregation) where column names are known
    # Exclude QBs so QB scrambles don't inflate the team carry denominator
    if rush_att_col and rush_att_col in pdf.columns and season_col and team_col and team_col in pdf.columns:
        pc = pos_col if pos_col and pos_col in pdf.columns else None
        non_qb = pdf[pdf[pc] != 'QB'].copy() if pc else pdf.copy()
        team_rush_src = non_qb.groupby([team_col, season_col])[rush_att_col].sum().reset_index()
        team_rush_src.rename(columns={team_col: 'team', season_col: 'season', rush_att_col: 'team_rush_att'}, inplace=True)
        result = result.merge(team_rush_src, on=['team','season'], how='left')
        buf = team_rush_src[team_rush_src['team']=='BUF']
        atl = team_rush_src[team_rush_src['team']=='ATL']
        pc_result = pos_col if pos_col and pos_col in result.columns else None
        result['rush_share'] = result.apply(
            lambda r: 0.0 if (pc_result and r.get(pc_result) == 'QB')
            else round(float(r['rush_att']) / float(r['team_rush_att']), 4)
            if float(r.get('team_rush_att') or 0) > 0 else 0.0, axis=1
        )
    else:
        result['rush_share'] = 0.0

    # ── Collapse multi-team (traded) player-seasons into ONE row ────────────
    # The groupby above includes team (required for per-stint rush_share
    # denominators), so a traded player yields one row per stint and only one
    # stint used to survive into the JSON — e.g. Tank Bigsby 2025 showed
    # games=1 instead of 12, poisoning ppg overrides. Collapse rules:
    #   · counting stats and games SUM across stints (weeks are disjoint —
    #     nflverse weekly data has one row per player-week)
    #   · target/air-yard/rush shares are stint-games-weighted means
    #   · team/identity fields come from the most recent stint (max week)
    key_cols = ['player_name', 'season'] + ([pos_col] if pos_col and pos_col in result.columns else [])
    dup_mask = result.duplicated(subset=key_cols, keep=False)
    if dup_mask.any():
        n_traded = result.loc[dup_mask, 'player_name'].nunique()
        sum_cols = [c for c in ['games','pass_yds','pass_td','pass_int','rush_yds','rush_td',
                                'rush_att','rec','rec_yds','rec_td','targets','air_yds']
                    if c in result.columns]
        share_cols = [c for c in ['target_share','air_yds_share','rush_share'] if c in result.columns]

        def _collapse(gr):
            gr = gr.sort_values('_last_week')
            out = gr.iloc[-1].copy()          # most recent stint: team + identity fields
            w = gr['games'].clip(lower=1)
            for c in sum_cols:
                out[c] = gr[c].sum()
            for c in share_cols:
                out[c] = round(float((gr[c] * w).sum() / w.sum()), 4)
            return out

        collapsed = (result[dup_mask]
                     .groupby(key_cols, as_index=False, group_keys=False)
                     .apply(_collapse))
        result = __import__('pandas').concat([result[~dup_mask], collapsed], ignore_index=True)
        print(f'[DELTA] Collapsed multi-team seasons for {n_traded} traded players')
    result = result.drop(columns=['_last_week'], errors='ignore')

    # Build headshot lookup from weekly data while pdf is in scope
    headshots = {}
    if 'headshot_url' in pdf.columns and name_col in pdf.columns:
        hs = pdf[[name_col, 'headshot_url']].dropna(subset=['headshot_url'])
        hs = hs[hs['headshot_url'].str.startswith('http', na=False)]
        for name, url in hs.groupby(name_col)['headshot_url'].first().items():
            headshots[name] = url
    print(f'[DELTA] Aggregated: {len(result)} player-seasons, {len(headshots)} headshots')
    print(f"[DELTA] Sample player names after agg: {result['player_name'].unique()[:5].tolist()}")
    return result, headshots

def match_names(agg, delta_names, no_data=None):
    nfl_names = agg['player_name'].unique()
    nfl_norm  = {norm(n): n for n in nfl_names}
    no_data   = no_data or set()

    print(f"[DELTA] nfl_norm size: {len(nfl_norm)}")
    print(f"[DELTA] 'josh allen' in nfl_norm: {'josh allen' in nfl_norm}")

    # Known aliases: DELTA name -> nflverse display name
    ALIASES = {
        'Chigoziem Okonkwo': 'Chig Okonkwo',
    }

    matched   = {}
    not_found = []

    for name in delta_names:
        # Skip players with no 2025 NFL data — rookies, long-term IR, etc.
        if name in no_data:
            continue
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

    eligible = len(delta_names) - len(no_data)
    print(f"[DELTA] Matched: {len(matched)}/{eligible} eligible players "
          f"({len(no_data)} skipped — no 2025 NFL data)")
    if not_found:
        print(f"[DELTA] Unmatched veterans (investigate): {not_found}")
    return matched

def fetch_redzone(seasons):
    # Fetch red zone (inside 20) carry and target counts from play-by-play.
    print("\n[DELTA] Fetching red zone data from PBP...")
    rz = {}
    try:
        for season in seasons:
            print(f"[DELTA] Loading PBP for {season}...")
            pbp = nfl.load_pbp(seasons=[season])
            pdf = pbp.to_pandas() if hasattr(pbp, "to_pandas") else pbp

            if "season_type" in pdf.columns:
                pdf = pdf[pdf["season_type"] == "REG"].copy()
            if "yardline_100" not in pdf.columns:
                print(f"[DELTA] No yardline_100 col in {season} PBP — skipping RZ")
                continue
            pdf = pdf[pdf["yardline_100"] <= 20].copy()

            # RZ targets
            rec_name_col = next((c for c in ["receiver_player_name","receiver_player_display_name"] if c in pdf.columns), None)
            if rec_name_col:
                pass_col = next((c for c in ["pass_attempt","pass"] if c in pdf.columns), None)
                tgt_plays = pdf[pdf[rec_name_col].notna()]
                if pass_col:
                    tgt_plays = tgt_plays[tgt_plays[pass_col] == 1]
                team_rz_tgt   = tgt_plays.groupby("posteam").size().to_dict()
                player_rz_tgt = tgt_plays.groupby(rec_name_col).size().to_dict()
            else:
                team_rz_tgt, player_rz_tgt = {}, {}
                print(f"[DELTA] No receiver name col in {season} PBP")

            # RZ carries
            rush_name_col = next((c for c in ["rusher_player_name","rusher_player_display_name"] if c in pdf.columns), None)
            if rush_name_col:
                rush_col = next((c for c in ["rush_attempt","rush"] if c in pdf.columns), None)
                rush_plays = pdf[pdf[rush_name_col].notna()]
                if rush_col:
                    rush_plays = rush_plays[rush_plays[rush_col] == 1]
                team_rz_car   = rush_plays.groupby("posteam").size().to_dict()
                player_rz_car = rush_plays.groupby(rush_name_col).size().to_dict()
            else:
                team_rz_car, player_rz_car = {}, {}
                print(f"[DELTA] No rusher name col in {season} PBP")

            rz[season] = {
                "player_rz_tgt": player_rz_tgt,
                "player_rz_car": player_rz_car,
                "team_rz_tgt":   team_rz_tgt,
                "team_rz_car":   team_rz_car,
            }
            print(f"[DELTA] RZ {season}: {len(player_rz_tgt)} receivers, {len(player_rz_car)} rushers")
    except Exception as e:
        print(f"[DELTA] Red zone fetch failed: {e}")
    return rz


def build_output(agg, matched, rz_data=None, headshots=None):
    players = {}

    def _rz_lookup(lookup_dict, nfl_name):
        if nfl_name in lookup_dict:
            return int(lookup_dict[nfl_name])
        # PBP uses abbreviated names (J.Chase) — try first initial + last name
        parts = nfl_name.split()
        if len(parts) >= 2:
            abbr = parts[0][0] + "." + parts[-1]
            if abbr in lookup_dict:
                return int(lookup_dict[abbr])
        return None  # None = not found, 0 = genuinely zero

    for delta_name, nfl_name in matched.items():
        rows = agg[agg["player_name"] == nfl_name]
        player_data = {}
        for season in SEASONS:
            srow = rows[rows["season"] == season]
            if srow.empty or int(srow.iloc[0].get("games", 0)) == 0:
                player_data[season] = None
                continue
            r = srow.iloc[0]
            rz  = rz_data.get(season, {}) if rz_data else {}
            player_data[season] = {
                "games":         int(r.get("games",    0)),
                "rec":           round(float(r.get("rec",      0)), 1),
                "rec_yds":       int(r.get("rec_yds",  0)),
                "rec_td":        int(r.get("rec_td",   0)),
                "rush_yds":      int(r.get("rush_yds", 0)),
                "rush_td":       int(r.get("rush_td",  0)),
                "rush_att":      int(r.get("rush_att", 0)),
                "rush_share":    round(float(r.get("rush_share", 0)), 4),
                "pass_yds":      int(r.get("pass_yds", 0)),
                "pass_td":       int(r.get("pass_td",  0)),
                "pass_int":      int(r.get("pass_int", 0)),
                "targets":       int(r.get("targets",  0)),
                "target_share":  round(float(r.get("target_share",  0)), 4),
                "air_yds_share": round(float(r.get("air_yds_share", 0)), 4),
                "rz_targets":    _rz_lookup(rz.get("player_rz_tgt", {}), nfl_name),
                "rz_carries":    _rz_lookup(rz.get("player_rz_car", {}), nfl_name),
            }
        players[delta_name] = player_data
    # Build delta_name → headshot_url mapping
    headshot_out = {}
    if headshots:
        for delta_name, nfl_name in matched.items():
            if nfl_name in headshots:
                headshot_out[delta_name] = headshots[nfl_name]
    print(f'[DELTA] Headshots matched: {len(headshot_out)}')
    return players, headshot_out

def spot_check(players, season=2025):
    checks = [
        ('Josh Allen',      0.0, 4),
        ("Ja'Marr Chase",   0.5, 4),
        ('Bijan Robinson',  0.5, 4),
        ('Trey McBride',    1.0, 4),
        ('Justin Jefferson',0.5, 4),
    ]
    print(f"\n[DELTA] Spot check ({season}, scoring: 4PT pass TD):")
    for name, ppr, pass_td_pts in checks:
        s = players.get(name, {}).get(season)
        if not s or not s.get("games"):
            print(f"  {name}: no data"); continue
        pts = (s["rec"]*ppr + s["rec_yds"]*0.1 + s["rec_td"]*6
             + s["rush_yds"]*0.1 + s["rush_td"]*6
             + s["pass_yds"]*0.04 + s["pass_td"]*pass_td_pts - s["pass_int"]*2)
        tgt_s  = f"tgt_share:{s.get('target_share','—')}"
        air_s  = f"air_yds_share:{s.get('air_yds_share','—')}"
        rz_t   = f"rz_tgt:{s.get('rz_targets','—')}"
        rz_c   = f"rz_car:{s.get('rz_carries','—')}"
        ra     = f"rush_att:{s.get('rush_att','—')}"
        print(f"  {name}: {s['games']}g → {round(pts/s['games'],1)} PPG | {tgt_s} {air_s} rush_share:{s.get('rush_share','—')} {ra} {rz_t} {rz_c}")

def fetch_contracts(delta_names):
    """Fetch active NFL contracts from nflverse (sourced from OTC)"""
    print("\n[DELTA] Fetching contracts from nflverse/OTC...")
    
    try:
        contracts_df = nfl.load_contracts()
        pdf = contracts_df.to_pandas() if hasattr(contracts_df, 'to_pandas') else contracts_df
        
        # Active contracts only
        if 'is_active' in pdf.columns:
            pdf = pdf[pdf['is_active'] == True].copy()
        
        print(f"[DELTA] Active contracts: {len(pdf)}")
        print(f"[DELTA] Contract columns: {list(pdf.columns)[:15]}")
        
        # Build name lookup
        name_col = next((c for c in ['player','player_name','name'] if c in pdf.columns), None)
        if not name_col:
            print("[DELTA] Could not find player name column in contracts")
            return {}
        
        # Normalize names for matching
        pdf['norm_name'] = pdf[name_col].apply(norm)
        # Also create a no-apostrophe version for fuzzy matching
        pdf['norm_name_clean'] = pdf[name_col].apply(
            lambda x: norm(str(x).replace("'","").replace("’",""))
        )
        
        contracts = {}
        not_found = []
        
        # Contract-specific aliases
        CONTRACT_ALIASES = {
            "Ja'Marr Chase": "Ja'Marr Chase",
            'Chigoziem Okonkwo': 'Chig Okonkwo',
        }
        
        for delta_name in delta_names:
            # Try alias first
            lookup = CONTRACT_ALIASES.get(delta_name, delta_name)
            key = norm(lookup)
            match = pdf[pdf['norm_name'] == key]
            
            # If no match, try the original name too
            if match.empty and lookup != delta_name:
                key = norm(delta_name)
                match = pdf[pdf['norm_name'] == key]
            
            # If still no match, try stripping all apostrophes
            if match.empty:
                key_clean = key.replace("'","")
                match = pdf[pdf['norm_name_clean'] == key_clean]
            
            if match.empty:
                # Try partial match
                words = key.split()
                found = None
                for length in range(len(words), 1, -1):
                    partial = ' '.join(words[:length])
                    cands = pdf[pdf['norm_name'].str.startswith(partial)]
                    if len(cands) == 1:
                        found = cands.iloc[0]
                        break
                if found is not None:
                    match = pd.DataFrame([found])
            
            if not match.empty:
                # Take the contract with latest end year (most recent extension)
                match = match.copy()
                match['_end'] = match.apply(
                    lambda r: int(r.get('year_signed', 2024) or 2024) + int(r.get('years', 1) or 1) - 1,
                    axis=1
                )
                row = match.sort_values('_end', ascending=False).iloc[0]
                # Calculate contract end year
                year_signed = int(row.get('year_signed', 2024) or 2024)
                years = int(row.get('years', 1) or 1)
                end_year = year_signed + years - 1
                
                # APY/value are in dollars not millions in nflverse
                # Divide by 1M for display
                apy_raw   = float(row.get('apy',   0) or 0)
                value_raw = float(row.get('value', 0) or 0)
                guar_raw  = float(row.get('guaranteed', 0) or 0)
                # nflverse stores in thousands or full dollars — detect scale
                aav_m = apy_raw / 1e6 if apy_raw > 1000 else apy_raw
                tot_m = value_raw / 1e6 if value_raw > 1000 else value_raw
                gua_m = guar_raw / 1e6 if guar_raw > 1000 else guar_raw

                contracts[delta_name] = {
                    'team':        str(row.get('team', '')),
                    'year_signed': year_signed,
                    'years':       years,
                    'end_year':    end_year,
                    'aav':         round(aav_m, 2),
                    'total':       round(tot_m, 2),
                    'guaranteed':  round(gua_m, 2),
                    'is_active':   True,
                }
            else:
                not_found.append(delta_name)
        
        print(f"[DELTA] Contracts matched: {len(contracts)}/{len(delta_names)}")
        vet_not_found = [n for n in not_found if n not in [
            'Jeremiyah Love','Carnell Tate','Fernando Mendoza','Jordyn Tyson',
            'Kenyon Sadiq','Makai Lemon','Omar Cooper','Jadarian Price',
            'Denzel Boston','Germie Bernard','Eli Stowers','Marlin Klein',
            'Max Klare','Carson Beck','Sam Roush','Antonio Williams',
            'Oscar Delp','Malachi Fields','Zachariah Branch','Chris Brazzell II',
            'Ted Hurst','Drew Allar','Will Kacmarek'
        ]]
        if vet_not_found:
            print(f"[DELTA] Unmatched veterans: {vet_not_found[:10]}")
        
        return contracts
        
    except Exception as e:
        print(f"[DELTA] Contract fetch failed: {e}")
        return {}

def main():
    print(f"[DELTA] Starting at {datetime.now(timezone.utc).isoformat()}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    delta_names, no_data = get_delta_players()
    print(f"[DELTA] {len(delta_names)} players in DELTA RAW ({len(no_data)} with no 2025 NFL data)")

    agg, headshots = fetch_season_stats()
    matched  = match_names(agg, delta_names, no_data)
    rz_data  = fetch_redzone(SEASONS)
    players, headshot_out = build_output(agg, matched, rz_data, headshots)

    output = {
        'fetched': datetime.now(timezone.utc).isoformat(),
        'seasons': SEASONS,
        'note':    'Raw stats — PPG calculated client-side per scoring format dropdown',
        'players': players,
        'headshots': headshot_out,
    }
    OUT_FILE.write_text(json.dumps(output, indent=2))
    kb = len(json.dumps(output)) // 1024
    print(f"[DELTA] player-stats.json written ({kb}KB, {len(players)} players)")
    spot_check(players)
    
    # 2. Fetch contracts
    contracts = fetch_contracts(delta_names)
    
    # Write contracts to separate file
    contracts_output = {
        'fetched': datetime.now(timezone.utc).isoformat(),
        'note': 'Active NFL contracts from nflverse/OTC. end_year = year_signed + years - 1.',
        'contracts': contracts,
    }
    contracts_file = OUT_DIR / "player-contracts.json"
    contracts_file.write_text(json.dumps(contracts_output, indent=2))
    kb = len(json.dumps(contracts_output)) // 1024
    print(f"[DELTA] player-contracts.json written ({kb}KB, {len(contracts)} contracts)")
    
    # Spot check key contracts
    print("\n[DELTA] Contract spot check:")
    for name in ['Josh Allen','Breece Hall',"Ja'Marr Chase",'Bijan Robinson','Trey McBride']:
        c = contracts.get(name)
        if c:
            print(f"  {name}: {c['years']}yr signed {c['year_signed']} → expires {c['end_year']}, AAV ${c['aav']:.1f}M, total ${c['total']:.1f}M")
        else:
            print(f"  {name}: NOT FOUND")

if __name__ == '__main__':
    main()
