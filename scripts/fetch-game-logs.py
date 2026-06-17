#!/usr/bin/env python3
"""
DELTA Game-Log Fetcher — per-game stat lines + snap counts for Start Profiles.
Mirrors fetch-player-stats.py conventions (nflreadpy, DELTA RAW-name scoping,
norm/match_names). Unlike that script, it keeps stats PER GAME (not aggregated)
and joins weekly OFFENSIVE SNAP COUNTS so the app can build Hit/Miss/Elite
profiles with the correct "games missed" exclusion.

DNP RULE (the whole point of pulling snaps):
  A game is EMITTED only if the player was ACTIVE that week — offense_snaps >= 1,
  OR he recorded a real stat line (if he produced, he played). A true inactive
  game (0 snaps, no stats) appears in NEITHER feed and is excluded by omission.
  Result the app sees: a 0-point emitted game = played-and-did-nothing = MISS;
  a missed game simply isn't in the list, so it never counts against miss rate.

Raw components are baked; the APP computes fantasy points per scoring format
(same as it already does for season stats). Point formula used for the in-script
spot check matches the threshold derivation:
  pass_yds*.04 + pass_td*4 + pass_int*-2 + rush_yds*.1 + rush_td*6
  + rec*PPR + rec_yds*.1 + rec_td*6 + fum_lost*-2 + two_pt*2 + ret_td*6
"""

import json, os, re, unicodedata
from datetime import datetime, timezone
from pathlib import Path

SEASONS    = [2023, 2024, 2025]   # matches player-stats.json; extend for deeper history (costs file size)
OUT_DIR    = Path(__file__).parent.parent / "data"
OUT_FILE   = OUT_DIR / "game-logs.json"
INDEX_HTML = Path(__file__).parent.parent / "index.html"

# ── helpers mirrored from fetch-player-stats.py (kept in sync intentionally) ──
def norm(name):
    name = unicodedata.normalize('NFKD', str(name))
    name = re.sub(r"[^a-z0-9\s]", '', name.lower())
    name = re.sub(r'\b(jr|sr|ii|iii|iv)\b', '', name)
    return re.sub(r'\s+', ' ', name).strip()

def get_delta_players():
    if not INDEX_HTML.exists():
        return [], set()
    html  = INDEX_HTML.read_text(encoding='utf-8')
    start = html.find('const RAW=[')
    end   = html.find('\nconst PICKS=', start)
    block = html[start:end]
    names = re.findall(r"n:'([^']+)'", block) + re.findall(r'n:"([^"]+)"', block)
    no_data = set()
    for m in re.finditer(r"n:'([^']+)'[^}]*?,g25:(\d+)", block):
        if m.group(2) == '0': no_data.add(m.group(1))
    for m in re.finditer(r'n:"([^"]+)"[^}]*?,g25:(\d+)', block):
        if m.group(2) == '0': no_data.add(m.group(1))
    return names, no_data

def match_names(nfl_names, delta_names, no_data=None):
    nfl_norm = {norm(n): n for n in nfl_names}
    no_data  = no_data or set()
    ALIASES  = {'Chigoziem Okonkwo': 'Chig Okonkwo'}
    matched, not_found = {}, []
    for name in delta_names:
        key = norm(ALIASES.get(name, name))
        if key in nfl_norm:
            matched[name] = nfl_norm[key]; continue
        # Seeded-zero players (g25:0 from expansion): attempt exact match above
        # so veterans get their logs, but skip the risky partial fallback so a
        # genuine no-NFL rookie can't partial-match a similarly named veteran.
        if name in no_data:
            continue
        words, found = key.split(), None
        for length in range(len(words), 1, -1):
            cands = [v for k, v in nfl_norm.items() if k.startswith(' '.join(words[:length]))]
            if len(cands) == 1: found = cands[0]; break
        if found: matched[name] = found
        else: not_found.append(name)
    print(f"[DELTA] Matched {len(matched)}/{len(delta_names)} players; unmatched: {not_found[:10]}")
    return matched

# ── column detection (nflverse names drift across versions) ──
def pick(df, *opts):
    return next((o for o in opts if o in df.columns), None)

def _num(row, c):
    if not c: return 0.0
    v = row.get(c)
    try: return float(v) if v is not None and v == v else 0.0   # NaN-safe
    except Exception: return 0.0

# ── PURE transform (no network) — unit-tested against synthetic frames ──
def build_game_logs(weekly_pdf, snaps_pdf, matched):
    """weekly_pdf/snaps_pdf: pandas DataFrames. matched: {delta_name: nfl_display_name}."""
    w = weekly_pdf
    nc   = pick(w, 'player_display_name')
    sc   = pick(w, 'season', 'year')
    wk   = pick(w, 'week', 'game_week')
    py   = pick(w, 'passing_yards', 'pass_yards')
    pt   = pick(w, 'passing_tds')
    pin  = pick(w, 'passing_interceptions', 'interceptions')
    ry   = pick(w, 'rushing_yards')
    rt   = pick(w, 'rushing_tds')
    rec  = pick(w, 'receptions', 'rec')
    rey  = pick(w, 'receiving_yards')
    ret  = pick(w, 'receiving_tds')
    # fumbles lost / 2pt / special TDs (sum components if present)
    fl_cols = [c for c in ['sack_fumbles_lost','rushing_fumbles_lost','receiving_fumbles_lost'] if c in w.columns]
    tp_cols = [c for c in ['passing_2pt_conversions','rushing_2pt_conversions','receiving_2pt_conversions'] if c in w.columns]
    sttd    = pick(w, 'special_teams_tds')

    # weekly stat lookup keyed (norm_name, season, week)
    wk_lookup = {}
    for _, r in w.iterrows():
        key = (norm(r.get(nc)), int(_num(r, sc)), int(_num(r, wk)))
        wk_lookup[key] = {
            'py': _num(r, py), 'pt': _num(r, pt), 'pi': _num(r, pin),
            'ry': _num(r, ry), 'rt': _num(r, rt),
            'rec': _num(r, rec), 'rey': _num(r, rey), 'ret': _num(r, ret),
            'fl': sum(_num(r, c) for c in fl_cols),
            'tp': sum(_num(r, c) for c in tp_cols),
            'rtd': _num(r, sttd),
        }

    # snap lookup keyed (norm_name, season, week) -> offense pct/snaps
    s = snaps_pdf
    snc = pick(s, 'player', 'player_display_name', 'pfr_player_name')
    ssc = pick(s, 'season')
    swk = pick(s, 'week')
    osn = pick(s, 'offense_snaps')
    opc = pick(s, 'offense_pct')
    snap_lookup = {}
    if s is not None and snc:
        for _, r in s.iterrows():
            key = (norm(r.get(snc)), int(_num(r, ssc)), int(_num(r, swk)))
            snap_lookup[key] = {'snaps': _num(r, osn), 'pct': _num(r, opc)}

    def has_production(st):
        return any(st[k] for k in ('py','pt','pi','ry','rt','rec','rey','ret','fl','tp','rtd'))

    games = {}
    for delta_name, nfl_name in matched.items():
        nkey = norm(nfl_name)
        keys = sorted({k for k in wk_lookup if k[0] == nkey} | {k for k in snap_lookup if k[0] == nkey},
                      key=lambda k: (k[1], k[2]))
        logs = []
        for (_, season, week) in keys:
            st   = wk_lookup.get((nkey, season, week))
            snap = snap_lookup.get((nkey, season, week))
            snaps = snap['snaps'] if snap else 0.0
            pct   = snap['pct']   if snap else 0.0
            active = (snaps >= 1) or (st is not None and has_production(st))
            if not active:
                continue   # 0 snaps + no production = DNP → excluded
            st = st or {k: 0.0 for k in ('py','pt','pi','ry','rt','rec','rey','ret','fl','tp','rtd')}
            logs.append({
                's': season, 'w': week, 'snp': round(pct, 2),
                'py': round(st['py']), 'pt': round(st['pt']), 'pi': round(st['pi']),
                'ry': round(st['ry']), 'rt': round(st['rt']),
                'rec': round(st['rec']), 'rey': round(st['rey']), 'ret': round(st['ret']),
                'fl': round(st['fl']), 'tp': round(st['tp']), 'rtd': round(st['rtd']),
            })
        if logs:
            games[delta_name] = logs
    return games

# ── point formula for spot-check (app recomputes live per format) ──
def game_points(g, ppr=0.5, te_prem=0.0):
    return (g['py']*0.04 + g['pt']*4 + g['pi']*-2 + g['ry']*0.1 + g['rt']*6
            + g['rec']*(ppr+te_prem) + g['rey']*0.1 + g['ret']*6
            + g['fl']*-2 + g['tp']*2 + g['rtd']*6)

def main():
    print(f"[DELTA] Game logs start {datetime.now(timezone.utc).isoformat()}")
    try:
        import nflreadpy as nfl
    except ImportError:
        os.system("pip install 'nflreadpy@git+https://github.com/nflverse/nflreadpy' polars pyarrow pandas --quiet")
        import nflreadpy as nfl

    delta_names, no_data = get_delta_players()
    print(f"[DELTA] {len(delta_names)} DELTA players ({len(no_data)} no-2025-data)")

    wdf = nfl.load_player_stats(seasons=SEASONS)
    wpdf = wdf.to_pandas() if hasattr(wdf, 'to_pandas') else wdf
    if 'season_type' in wpdf.columns:
        wpdf = wpdf[wpdf['season_type'] == 'REG'].copy()
    print(f"[DELTA] weekly stat rows: {len(wpdf)}")

    try:
        sdf = nfl.load_snap_counts(seasons=SEASONS)
        spdf = sdf.to_pandas() if hasattr(sdf, 'to_pandas') else sdf
        if 'game_type' in spdf.columns:
            spdf = spdf[spdf['game_type'] == 'REG'].copy()
        print(f"[DELTA] snap rows: {len(spdf)}")
    except Exception as e:
        print(f"[DELTA] WARNING: load_snap_counts failed ({e}); emitting all stat games as active.")
        import pandas as pd
        spdf = pd.DataFrame(columns=['player','season','week','offense_snaps','offense_pct'])

    matched = match_names(wpdf['player_display_name'].dropna().unique(), delta_names, no_data)
    games   = build_game_logs(wpdf, spdf, matched)

    output = {
        'fetched': datetime.now(timezone.utc).isoformat(),
        'seasons': SEASONS,
        'sample':  False,
        'note': ('Per-game raw stat lines + offense snap %. Only ACTIVE games emitted '
                 '(>=1 snap or recorded production); inactive games omitted so they never '
                 'count as misses. App computes fantasy points per scoring format. '
                 'Keys: s=season w=week snp=offense_pct py/pt/pi=pass yds/td/int '
                 'ry/rt=rush yds/td rec/rey/ret=rec/rec yds/rec td fl=fum lost tp=2pt rtd=ret/ST td.'),
        'games': games,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(output, separators=(',', ':')))
    kb = len(json.dumps(output)) // 1024
    total_games = sum(len(v) for v in games.values())
    print(f"[DELTA] game-logs.json written ({kb}KB, {len(games)} players, {total_games} active games)")

    print("\n[DELTA] Spot check (0.5PPR, 4pt passTD) — recent games for a few players:")
    for name in ['Josh Allen', "Ja'Marr Chase", 'Bijan Robinson', 'Trey McBride']:
        gl = games.get(name, [])
        recent = [g for g in gl if g['s'] == 2025][-3:]
        if recent:
            tep = 1.0 if name == 'Trey McBride' else 0.0  # TE premium for spot-check only
            pts = [round(game_points(g, 0.5, tep), 1) for g in recent]
            print(f"  {name}: last 3 of 2025 → {pts} (weeks {[g['w'] for g in recent]}, snap% {[g['snp'] for g in recent]})")
        else:
            print(f"  {name}: no 2025 games")

if __name__ == '__main__':
    main()
