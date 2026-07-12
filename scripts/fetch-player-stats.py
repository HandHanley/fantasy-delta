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
INDEX_HTML = Path(__file__).parent.parent / "delta-engine.js"  # RAW array moved here from index.html

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
    # name → (team, pos): RAW's team field is the maintained current-team source
    # (it tracks FA moves, e.g. Fields NYJ→KC), which the QB role flags rely on.
    meta = {}
    for m in re.finditer(r"n:'([^']+)',t:'([^']+)',p:'([^']+)'", block):
        meta[m.group(1)] = (m.group(2), m.group(3))
    for m in re.finditer(r'n:"([^"]+)",t:\'([^\']+)\',p:\'([^\']+)\'', block):
        meta[m.group(1)] = (m.group(2), m.group(3))
    return names, no_data, meta

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
    pass_att_col= col('attempts', 'passing_attempts', 'pass_attempts')
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
    for c in [pass_yd_col, pass_td_col, pass_att_col, pass_int_col, rush_yd_col, rush_td_col,
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
        ('pass_att',       pass_att_col),
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
        sum_cols = [c for c in ['games','pass_yds','pass_td','pass_att','pass_int','rush_yds','rush_td',
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
    # Start counts (weeks with >=15 pass attempts) for the QB role flags,
    # broken out per (player, team) for 2025 AND 2024. Per-team granularity is
    # what distinguishes a true incumbent (started for THIS team) from an
    # established-elsewhere newcomer (Tua arriving in Atlanta), and 2024 counts
    # power the franchise-starter exemption (Burrow's injury fill-in must not
    # read as an incumbent over him).
    qb_starts = {'2025': {}, '2024': {}}
    att_col = col('attempts', 'passing_attempts', 'pass_attempts')
    if att_col and season_col and name_col and team_col:
        for season in (2025, 2024):
            rows = pdf[(pdf[season_col] == season) & (pdf[att_col].fillna(0) >= 15)]
            for (nm, tm), cnt in rows.groupby([name_col, team_col]).size().items():
                e = qb_starts[str(season)].setdefault(nm, {'total': 0, 'teams': {}})
                e['total'] += int(cnt)
                e['teams'][tm] = int(cnt)
        print(f"[DELTA] start counts: {len(qb_starts['2025'])} players in 2025, {len(qb_starts['2024'])} in 2024")
    else:
        print('[DELTA] WARNING: no attempts/team column — QB role flags will be empty')

    print(f'[DELTA] Aggregated: {len(result)} player-seasons, {len(headshots)} headshots')
    print(f"[DELTA] Sample player names after agg: {result['player_name'].unique()[:5].tolist()}")
    return result, headshots, qb_starts

def fetch_depth_chart_qbs():
    """Best-effort 2026 QB depth chart: {team: [qb display names in depth order]}.
    Returns None when unavailable (common pre-camp) — callers fall back to
    2025 incumbency. Defensive on schema: nflverse depth-chart columns vary."""
    try:
        loader = getattr(nfl, 'load_depth_charts', None)
        if loader is None:
            print('[DELTA] depth charts: loader not available in nflreadpy — skipping')
            return None
        df = loader(seasons=[2026])
        pdf = df.to_pandas() if hasattr(df, 'to_pandas') else df
        if pdf is None or len(pdf) == 0:
            print('[DELTA] depth charts: empty for 2026 — skipping')
            return None
        def c(*opts):
            return next((o for o in opts if o in pdf.columns), None)
        team_c = c('club_code', 'team', 'team_abbr')
        pos_c  = c('position', 'pos', 'depth_chart_position')
        rank_c = c('depth_team', 'depth_position', 'rank')
        name_c = c('full_name', 'player_name', 'football_name')
        week_c = c('week')
        if not all([team_c, pos_c, rank_c, name_c]):
            print(f'[DELTA] depth charts: unrecognized schema {list(pdf.columns)[:12]} — skipping')
            return None
        qb = pdf[pdf[pos_c] == 'QB'].copy()
        if week_c:
            qb = qb[qb[week_c] == qb[week_c].max()]
        qb['_rank'] = qb[rank_c].astype(str).str.extract(r'(\d+)').astype(float)
        out = {}
        for team, gr in qb.groupby(team_c):
            out[team] = list(gr.sort_values('_rank')[name_c])
        print(f'[DELTA] depth charts: 2026 QB order loaded for {len(out)} teams')
        return out
    except Exception as e:
        print(f'[DELTA] depth charts unavailable ({e}) — falling back to 2025 incumbency')
        return None

def fetch_current_teams():
    """Best-effort current-team map from nflverse 2026 rosters, keyed by
    (name, position): {(display_name, pos): team}. Position is REQUIRED in the
    key — matching on name alone let same-named defenders/rookies hijack skill
    players (the June 2026 bug: WR DeVonta Smith dragged to CAR by a Panthers
    UDFA cornerback; WR Justin Jefferson to CLE by a Browns rookie LB; RB
    Quinshon Judkins to GB). We also drop any (name,pos) that is itself
    ambiguous *within offensive skill positions* (two real skill players, same
    name, same position on different teams) — there is no safe pick, so we
    defer to RAW. Returns None when unavailable; callers fall back to baked
    teams. Restricted to QB/RB/WR/TE: DELTA never tracks other positions, and
    excluding them removes the entire cross-position collision surface."""
    SKILL = {'QB', 'RB', 'WR', 'TE'}
    try:
        loader = getattr(nfl, 'load_rosters', None) or getattr(nfl, 'load_rosters_weekly', None)
        if loader is None:
            print('[DELTA] roster feed: loader not available in nflreadpy — skipping')
            return None
        df = loader(seasons=[2026])
        pdf = df.to_pandas() if hasattr(df, 'to_pandas') else df
        if pdf is None or len(pdf) == 0:
            print('[DELTA] roster feed: empty for 2026 — skipping')
            return None
        def c(*opts):
            return next((o for o in opts if o in pdf.columns), None)
        name_c = c('full_name', 'player_name', 'display_name', 'football_name')
        team_c = c('team', 'club_code', 'recent_team')
        pos_c  = c('position', 'pos', 'depth_chart_position')
        week_c = c('week')
        if not name_c or not team_c or not pos_c:
            print(f'[DELTA] roster feed: unrecognized schema {list(pdf.columns)[:10]} — skipping (need name/team/POSITION)')
            return None
        if week_c:
            pdf = pdf[pdf[week_c] == pdf[week_c].max()]
        pdf = pdf.dropna(subset=[name_c, team_c, pos_c])
        pdf = pdf[pdf[pos_c].isin(SKILL)]
        # (name, pos) -> set of teams seen; only emit unambiguous ones
        from collections import defaultdict
        seen = defaultdict(set)
        for _, row in pdf.iterrows():
            seen[(row[name_c], row[pos_c])].add(row[team_c])
        out, ambiguous = {}, []
        for (nm, pos), teams in seen.items():
            if len(teams) == 1:
                out[(nm, pos)] = next(iter(teams))
            else:
                ambiguous.append(f'{nm}/{pos}:{sorted(teams)}')
        if ambiguous:
            print(f'[DELTA] roster feed: {len(ambiguous)} ambiguous (name,pos) skipped — {ambiguous[:6]}')
        print(f'[DELTA] roster feed: 2026 skill-position teams for {len(out)} (name,pos) keys')
        return out
    except Exception as e:
        print(f'[DELTA] roster feed unavailable ({e}) — using RAW baked teams')
        return None

def compute_qb_backup_flags(meta, matched, qb_starts, depth, roster_teams=None):
    """Conservative QB backup flags — only when an UNAMBIGUOUS established
    incumbent sits ahead. Rules (binary, asymmetric, QB-only by design — depth
    info is never read for other positions, where snap/target share already
    measure opportunity):
      · incumbent = QB with >=10 start-weeks in 2025 (attempts>=15)
      · depth-chart layer (when published): flag rank>1 QBs behind an
        established rank-1
      · incumbency fallback (offseason): flag a <10-start QB sharing a RAW
        team with an established QB; two established QBs on one roster =
        ambiguous = no flag (innocent until proven backup)"""
    ESTABLISHED = 10      # 2025 start-weeks to count as an established starter
    TEAM_INCUMBENT = 6    # starts WITH this team in 2025 to be a true incumbent
    CLEAR_BACKUP = 2      # q's own 2025 starts at/below this = clearly not a starter
    FRANCHISE_PRIOR = 10  # 2024 starts with THIS team = franchise starter (injury exemption)
    EMPTY = {'total': 0, 'teams': {}}
    s25, s24 = qb_starts.get('2025', {}), qb_starts.get('2024', {})
    flags = {}
    qb_team = {n: tp[0] for n, tp in meta.items() if tp[1] == 'QB'}
    for q, raw_team in qb_team.items():
        nfl_q = matched.get(q, q)
        team = (roster_teams or {}).get((nfl_q, 'QB')) or raw_team   # roster feed wins (FA/trade moves)
        q25 = s25.get(nfl_q, EMPTY)
        if depth and team in depth:
            # Depth-chart layer: present-state truth, may flag anyone behind an
            # established rank-1 — including exemption cases, since a published
            # camp chart outranks our offseason inference.
            order = depth[team]
            if nfl_q in order and order.index(nfl_q) > 0:
                starter = order[0]
                if s25.get(starter, EMPTY)['total'] >= ESTABLISHED:
                    flags[q] = {'role': 'backup', 'behind': starter, 'source': 'depth-chart'}
            continue  # depth chart spoke for this team — no fallback
        if q25['total'] >= ESTABLISHED:
            continue  # established themselves — never flagged by incumbency
        # Franchise-starter exemption (the Burrow case): a QB who started >=10
        # games for THIS team in 2024 and missed 2025 to injury must not read
        # as a backup to his own fill-in — the fill-in's starts are a symptom
        # of the injury, not an incumbency.
        if s24.get(nfl_q, EMPTY)['teams'].get(team, 0) >= FRANCHISE_PRIOR:
            continue
        best = None
        for o, o_raw_team in qb_team.items():
            if o == q:
                continue
            nfl_o = matched.get(o, o)
            o_team = (roster_teams or {}).get((nfl_o, 'QB')) or o_raw_team
            if o_team != team:
                continue
            o25 = s25.get(nfl_o, EMPTY)
            if o25['total'] < ESTABLISHED:
                continue
            # Newcomer-vet rule (the Penix case): an established-ELSEWHERE
            # arrival does not unseat the team's own recent starter — that is
            # an open competition, not a depth fact. He IS an incumbent over
            # clear backups and rookies (q with <=2 starts of his own).
            if o25['teams'].get(team, 0) < TEAM_INCUMBENT and q25['total'] > CLEAR_BACKUP:
                continue
            if best is None or o25['total'] > best[1]:
                best = (o, o25['total'])
        if best:
            flags[q] = {'role': 'backup', 'behind': best[0], 'source': 'incumbency-2025'}
    print(f'[DELTA] QB backup flags ({len(flags)}):')
    for q, f in flags.items():
        print(f"  {q} → behind {f['behind']} ({f['source']})")
    return flags

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
        lookup = ALIASES.get(name, name)
        key    = norm(lookup)

        if key in nfl_norm:
            matched[name] = nfl_norm[key]
        elif name in no_data:
            # Seeded-zero player (g25:0 placeholder from the universe expansion).
            # We STILL attempt an exact normalized match above — that's how
            # veterans like Najee Harris / Nick Chubb / Tank Dell get their real
            # stats. But we do NOT use the risky partial-match fallback for them,
            # because a genuine no-NFL rookie could partial-match a similarly
            # named veteran. No exact hit → genuinely no data, leave unmatched.
            pass
        else:
            # Partial match fallback (core roster players only)
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

    print(f"[DELTA] Matched: {len(matched)}/{len(delta_names)} players "
          f"({len(delta_names) - len(matched)} unmatched — genuine no-NFL-data + name misses)")
    if not_found:
        print(f"[DELTA] Unmatched veterans (investigate): {not_found}")
    return matched

def _epa_from_pbp(pdf, season, epa_out):
    """Compute QB and RB EPA/play for one season's PBP frame, accumulate into
    epa_out[name][f'e{yy}']. QB = mean(qb_epa) over dropbacks; RB = mean(epa)
    over rush attempts. WR/TE are intentionally NOT computed here — their
    efficiency input is hand-curated YPRR (no free routes-run source), so the
    runtime keeps the hand EPA/YPRR table for receivers."""
    yy = str(season)[-2:]
    key = f'e{yy}'
    cols = set(pdf.columns)
    # ---- QB EPA/play ----
    qb_epa_col = 'qb_epa' if 'qb_epa' in cols else ('epa' if 'epa' in cols else None)
    passer_col = next((c for c in ['passer_player_name','passer_player_display_name','passer'] if c in cols), None)
    if qb_epa_col and passer_col:
        db_col = next((c for c in ['qb_dropback','pass'] if c in cols), None)
        qb_plays = pdf[pdf[passer_col].notna()]
        if db_col:
            qb_plays = qb_plays[qb_plays[db_col] == 1]
        g = qb_plays.groupby(passer_col)[qb_epa_col].agg(['mean','count'])
        for name, row in g.iterrows():
            if row['count'] >= 50:  # min dropbacks for a stable season figure
                epa_out.setdefault(name, {})[key] = round(float(row['mean']), 3)
    # ---- RB EPA/play (rushing) ----
    epa_col = 'epa' if 'epa' in cols else None
    rusher_col = next((c for c in ['rusher_player_name','rusher_player_display_name','rusher'] if c in cols), None)
    if epa_col and rusher_col:
        rush_col = next((c for c in ['rush_attempt','rush'] if c in cols), None)
        rush_plays = pdf[pdf[rusher_col].notna()]
        if rush_col:
            rush_plays = rush_plays[rush_plays[rush_col] == 1]
        g = rush_plays.groupby(rusher_col)[epa_col].agg(['mean','count'])
        for name, row in g.iterrows():
            if row['count'] >= 40:  # min carries for a stable season figure
                # don't overwrite a QB entry (scrambling QBs appear as rushers)
                e = epa_out.setdefault(name, {})
                if key not in e:
                    e[key] = round(float(row['mean']), 3)


def fetch_pbp(seasons):
    """Single PBP pass per season computing BOTH red-zone counts and QB/RB EPA.
    Loads one extra prior season for EPA depth (calcEPA weights e22 at 0.5)."""
    print("\n[DELTA] Fetching PBP (red zone + EPA)...")
    rz = {}
    epa_out = {}
    # EPA looks back one more year than the stats seasons (e22 weight in calcEPA)
    epa_seasons = sorted(set(seasons) | {min(seasons) - 1})
    for season in epa_seasons:
        try:
            print(f"[DELTA] Loading PBP for {season}...")
            pbp = nfl.load_pbp(seasons=[season])
            pdf = pbp.to_pandas() if hasattr(pbp, "to_pandas") else pbp
            if "season_type" in pdf.columns:
                pdf = pdf[pdf["season_type"] == "REG"].copy()
            # EPA for every season we load
            _epa_from_pbp(pdf, season, epa_out)
            # Red zone only for the core stats seasons
            if season in seasons:
                _redzone_from_pbp(pdf, season, rz)
        except Exception as e:
            print(f"[DELTA] PBP {season} failed: {e}")
    print(f"[DELTA] EPA computed for {len(epa_out)} players (QB/RB)")
    return rz, epa_out


def _redzone_from_pbp(pdf, season, rz):
    # Red zone (inside 20) carry and target counts for one season frame.
    if "yardline_100" not in pdf.columns:
        print(f"[DELTA] No yardline_100 col in {season} PBP — skipping RZ")
        return
    rzdf = pdf[pdf["yardline_100"] <= 20].copy()
    rec_name_col = next((c for c in ["receiver_player_name","receiver_player_display_name"] if c in rzdf.columns), None)
    if rec_name_col:
        pass_col = next((c for c in ["pass_attempt","pass"] if c in rzdf.columns), None)
        tgt_plays = rzdf[rzdf[rec_name_col].notna()]
        if pass_col:
            tgt_plays = tgt_plays[tgt_plays[pass_col] == 1]
        team_rz_tgt   = tgt_plays.groupby("posteam").size().to_dict()
        player_rz_tgt = tgt_plays.groupby(rec_name_col).size().to_dict()
    else:
        team_rz_tgt, player_rz_tgt = {}, {}
    rush_name_col = next((c for c in ["rusher_player_name","rusher_player_display_name"] if c in rzdf.columns), None)
    if rush_name_col:
        rush_col = next((c for c in ["rush_attempt","rush"] if c in rzdf.columns), None)
        rush_plays = rzdf[rzdf[rush_name_col].notna()]
        if rush_col:
            rush_plays = rush_plays[rush_plays[rush_col] == 1]
        team_rz_car   = rush_plays.groupby("posteam").size().to_dict()
        player_rz_car = rush_plays.groupby(rush_name_col).size().to_dict()
    else:
        team_rz_car, player_rz_car = {}, {}
    rz[season] = {
        "player_rz_tgt": player_rz_tgt,
        "player_rz_car": player_rz_car,
        "team_rz_tgt":   team_rz_tgt,
        "team_rz_car":   team_rz_car,
    }
    print(f"[DELTA] RZ {season}: {len(player_rz_tgt)} receivers, {len(player_rz_car)} rushers")


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
        # PBP uses abbreviated names (J.Chase). Suffixes broke the old fallback:
        # "Marvin Harrison Jr." -> parts[-1] = "Jr." -> "M.Jr." (never matches).
        # Build candidates with the suffix stripped AND retained, since PBP
        # sources are inconsistent about including it.
        parts = nfl_name.split()
        if len(parts) >= 2:
            SUFFIXES = {"Jr.", "Jr", "Sr.", "Sr", "II", "III", "IV", "V"}
            core = [p for p in parts if p not in SUFFIXES]
            cands = []
            if len(core) >= 2:
                cands.append(core[0][0] + "." + core[-1])                       # M.Harrison
                trail = parts[parts.index(core[-1]) + 1:] if core[-1] in parts else []
                if trail:
                    cands.append(core[0][0] + "." + core[-1] + " " + " ".join(trail))  # M.Harrison Jr.
            cands.append(parts[0][0] + "." + parts[-1])                          # legacy form, last
            for abbr in cands:
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
                "pass_att":      int(r.get("pass_att", 0)),
                "pass_int":      int(r.get("pass_int", 0)),
                "targets":       int(r.get("targets",  0)),
                "target_share":  round(float(r.get("target_share",  0)), 4),
                "air_yds_share": round(float(r.get("air_yds_share", 0)), 4),
                "rz_targets":    _rz_lookup(rz.get("player_rz_tgt", {}), nfl_name),
                "rz_carries":    _rz_lookup(rz.get("player_rz_car", {}), nfl_name),
            }
        players[delta_name] = player_data

    # ---- Derived metrics (no extra fetch — from the per-season data above) ----
    # REC_PG: receptions per game in the most recent season with games.
    # TS_DELTA: target-share change, latest season minus prior season (decimal).
    rec_pg, ts_delta = {}, {}
    for delta_name, pdata in players.items():
        latest = None
        for season in sorted(SEASONS, reverse=True):
            if pdata.get(season) and pdata[season].get('games'):
                latest = season
                break
        if latest is None:
            continue
        cur = pdata[latest]
        g = cur.get('games') or 0
        if g:
            rpg = (cur.get('rec') or 0) / g
            if rpg > 0:
                rec_pg[delta_name] = round(rpg, 2)
        # target-share delta vs the immediately prior season WITH games
        prior = None
        for season in sorted([s for s in SEASONS if s < latest], reverse=True):
            if pdata.get(season) and pdata[season].get('games'):
                prior = season
                break
        if prior is not None:
            d = (cur.get('target_share') or 0) - (pdata[prior].get('target_share') or 0)
            if abs(d) >= 0.005:  # only emit a meaningful move
                ts_delta[delta_name] = round(d, 3)
    print(f'[DELTA] Derived: {len(rec_pg)} rec/g, {len(ts_delta)} target-share deltas')

    # Build delta_name → headshot_url mapping
    headshot_out = {}
    if headshots:
        for delta_name, nfl_name in matched.items():
            if nfl_name in headshots:
                headshot_out[delta_name] = headshots[nfl_name]
    print(f'[DELTA] Headshots matched: {len(headshot_out)}')
    return players, headshot_out, rec_pg, ts_delta

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

def fetch_rb_snap_share(delta_names, meta):
    """Per-season RB snap share from nflverse snap counts, mapped to DELTA names.
    Returns {delta_name: [pct_2025, pct_2024, pct_2023, pct_2022]} (most-recent
    first, matching the hand RB_SNAP shape). Only RBs are emitted. A season the
    player didn't register snaps is 0. Returns {} on failure — runtime falls
    back to the hand RB_SNAP table."""
    out = {}
    try:
        SNAP_SEASONS = [2025, 2024, 2023, 2022]
        # per-season {nflverse_name: mean offense_pct across that player's games}
        by_season = {}
        for season in SNAP_SEASONS:
            try:
                df = nfl.load_snap_counts(seasons=[season])
                pdf = df.to_pandas() if hasattr(df, 'to_pandas') else df
            except Exception as e:
                print(f'[DELTA] snap counts {season} failed: {e}')
                by_season[season] = {}
                continue
            cols = set(pdf.columns)
            name_col = next((c for c in ['player','player_name','full_name','pfr_player_name'] if c in cols), None)
            pos_col  = next((c for c in ['position'] if c in cols), None)
            pct_col  = next((c for c in ['offense_pct','offense_snaps_pct','off_pct'] if c in cols), None)
            if not (name_col and pct_col):
                print(f'[DELTA] snap counts {season}: missing columns — skipping')
                by_season[season] = {}
                continue
            df2 = pdf
            if pos_col:
                df2 = df2[df2[pos_col] == 'RB']
            # offense_pct may be a fraction (0-1) or a percent (0-100); normalize to %.
            def to_pct(v):
                try:
                    v = float(v)
                except (ValueError, TypeError):
                    return None
                return v * 100.0 if v <= 1.0 else v
            agg = {}
            for _, row in df2.iterrows():
                nm = row.get(name_col)
                p = to_pct(row.get(pct_col))
                if nm and p is not None:
                    agg.setdefault(nm, []).append(p)
            by_season[season] = {nm: round(sum(v)/len(v), 1) for nm, v in agg.items()}

        # build a normalized index per season for matching
        rb_names = [dn for dn in delta_names if meta.get(dn, (None, None))[1] == 'RB']
        def season_norm_idx(d):
            idx = {}
            for k in d:
                idx.setdefault(norm(k), k)
            return idx
        norm_idx = {s: season_norm_idx(by_season.get(s, {})) for s in SNAP_SEASONS}
        for dn in rb_names:
            arr = []
            any_val = False
            for s in SNAP_SEASONS:
                hit = norm_idx[s].get(norm(dn))
                val = by_season[s].get(hit, 0) if hit else 0
                if val:
                    any_val = True
                arr.append(val)
            if any_val:
                out[dn] = arr
        print(f'[DELTA] RB snap share: {len(out)} RBs matched')
    except Exception as e:
        print(f'[DELTA] RB snap share fetch failed: {e}')
    return out


def fetch_draft_and_college(delta_names, meta):
    """Pull draft capital (year/round/pick) and college from nflverse, mapped to
    DELTA names. Retires the hand DRAFT_PICKS and COLLEGES tables and auto-fills
    them for the expanded universe. Returns (draft_map, college_map):
      draft_map[delta_name]   = {'y': year, 'r': round, 'p': overall_pick}
      college_map[delta_name] = 'College Name'
    Returns ({}, {}) on failure — runtime falls back to the baked tables."""
    draft_map, college_map, age_map = {}, {}, {}

    # Lightweight matcher: DELTA name -> key in a raw{nflverse_name: value} dict.
    # Reuses norm() (period/suffix/case-insensitive). Exact-normalized match
    # only; we do NOT do partial/startswith here because draft+college are
    # identity facts where a fuzzy hit (e.g. two "Mike Williams") is worse than
    # a miss that falls back to the baked table.
    DRAFT_ALIASES = {'Chigoziem Okonkwo': 'Chig Okonkwo'}
    def _match(raw, delta_names):
        rawnorm = {}
        for k in raw:
            rawnorm.setdefault(norm(k), k)
        out = {}
        for dn in delta_names:
            lk = DRAFT_ALIASES.get(dn, dn)
            hit = rawnorm.get(norm(lk))
            if hit is not None:
                out[dn] = hit
        return out

    # ---- DRAFT PICKS ----
    try:
        df = nfl.load_draft_picks()
        pdf = df.to_pandas() if hasattr(df, 'to_pandas') else df
        cols = set(pdf.columns)
        name_col = next((c for c in ['pfr_player_name','player_name','full_name','display_name'] if c in cols), None)
        yr_col   = next((c for c in ['season','draft_year','year'] if c in cols), None)
        rd_col   = next((c for c in ['round'] if c in cols), None)
        pk_col   = next((c for c in ['pick','overall','selection'] if c in cols), None)
        if name_col and yr_col and rd_col and pk_col:
            # newest pick per name wins (handles rare re-entry); build raw map by nflverse name
            raw = {}
            for _, row in pdf.iterrows():
                nm = row.get(name_col)
                if not nm or row.get(pk_col) is None:
                    continue
                try:
                    raw[nm] = {'y': int(row[yr_col]), 'r': int(row[rd_col]), 'p': int(row[pk_col])}
                except (ValueError, TypeError):
                    continue
            matched = _match(raw, delta_names)
            for dn, nfl_name in matched.items():
                draft_map[dn] = raw[nfl_name]
            print(f'[DELTA] draft capital: {len(draft_map)} DELTA players matched')
        else:
            print(f'[DELTA] draft picks: missing expected columns (have {sorted(cols)[:8]}...) — skipping')
    except Exception as e:
        print(f'[DELTA] draft picks fetch failed: {e}')

    # ---- COLLEGE ----
    try:
        df = nfl.load_players()
        pdf = df.to_pandas() if hasattr(df, 'to_pandas') else df
        cols = set(pdf.columns)
        name_col = next((c for c in ['display_name','full_name','player_name','football_name'] if c in cols), None)
        col_col  = next((c for c in ['college','college_name','college_conference'] if c in cols and 'conference' not in c), None)
        # age (years, 1-decimal) from birth_date if present — same dataset, one pass
        bd_col = next((c for c in ['birth_date','birthdate','birth_year'] if c in cols), None)
        if name_col and col_col:
            raw = {}
            raw_age = {}
            from datetime import date
            today = date.today()
            for _, row in pdf.iterrows():
                nm = row.get(name_col)
                if not nm:
                    continue
                cg = row.get(col_col)
                if cg and str(cg).strip() and str(cg).lower() != 'none':
                    raw[nm] = str(cg).strip()
                if bd_col:
                    bd = row.get(bd_col)
                    if bd is not None and str(bd).strip() and str(bd).lower() != 'none':
                        try:
                            s = str(bd)[:10]
                            y, m, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
                            age_yrs = (today - date(y, m, d)).days / 365.25
                            if 18 <= age_yrs <= 50:
                                raw_age[nm] = round(age_yrs, 1)
                        except (ValueError, TypeError):
                            pass
            matched = _match(raw, delta_names)
            for dn, nfl_name in matched.items():
                college_map[dn] = raw[nfl_name]
            age_matched = _match(raw_age, delta_names)
            for dn, nfl_name in age_matched.items():
                age_map[dn] = raw_age[nfl_name]
            print(f'[DELTA] college: {len(college_map)} matched · age: {len(age_map)} matched')
        else:
            print(f'[DELTA] college: missing expected columns — skipping')
    except Exception as e:
        print(f'[DELTA] college fetch failed: {e}')

    return draft_map, college_map, age_map


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

    delta_names, no_data, meta = get_delta_players()
    print(f"[DELTA] {len(delta_names)} players in DELTA RAW ({len(no_data)} with no 2025 NFL data)")

    agg, headshots, qb_starts = fetch_season_stats()
    matched  = match_names(agg, delta_names, no_data)
    roster_teams = fetch_current_teams()
    qb_roles = compute_qb_backup_flags(meta, matched, qb_starts, fetch_depth_chart_qbs(), roster_teams)
    # Team overrides for the runtime: only DELTA players the roster feed
    # resolves; RAW's baked team stays the fallback for everyone else.
    # Normalize feed abbreviations to DELTA's convention so we don't churn the
    # team field on pure abbreviation differences (feed JAX/LA/WSH/ARZ vs DELTA
    # JAC/LAR/WAS/ARI) — the runtime AL map aliases these anyway, but writing the
    # canonical form keeps the data clean and the "moved" log honest.
    TEAM_CANON = {'JAX': 'JAC', 'LA': 'LAR', 'WSH': 'WAS', 'ARZ': 'ARI'}
    team_overrides = {}
    if roster_teams:
        for dn, nfl_name in matched.items():
            pos = meta.get(dn, (None, None))[1]
            if not pos:
                continue
            t = roster_teams.get((nfl_name, pos))   # name AND position must agree
            if t:
                team_overrides[dn] = TEAM_CANON.get(t, t)
        moved = [f'{dn} {meta[dn][0]}->{t}' for dn, t in team_overrides.items() if dn in meta and meta[dn][0] != t]
        print(f'[DELTA] team overrides: {len(team_overrides)} resolved, {len(moved)} genuine moves: {moved[:20]}')
    rz_data, epa_raw = fetch_pbp(SEASONS)
    players, headshot_out, rec_pg, ts_delta = build_output(agg, matched, rz_data, headshots)

    # Map computed QB/RB EPA onto DELTA names. Only QB/RB are emitted — WR/TE
    # efficiency is the hand-curated YPRR layer (no free routes source), so the
    # runtime keeps the hand EPA table for receivers and merges this over it for
    # QB/RB. epa_raw is keyed by nflverse PBP names, which are ABBREVIATED
    # (J.Allen, B.Robinson) — NOT the full display names in `matched`. So we
    # match each DELTA QB/RB by building its abbreviated form (first initial +
    # last name) and looking it up in epa_raw, same approach as _rz_lookup.
    epa_out = {}
    qb_rb = [dn for dn, mt in meta.items() if mt[1] in ('QB', 'RB')]
    # normalized index of abbreviated PBP names → value
    epa_norm = {}
    for nfl_name, vals in epa_raw.items():
        epa_norm[norm(nfl_name)] = vals
    def _abbr(full):
        parts = full.replace("'", "").split()
        if len(parts) >= 2:
            return parts[0][0] + "." + " ".join(parts[1:])
        return full
    for dn in qb_rb:
        nfl_full = matched.get(dn)
        cand_names = []
        if nfl_full:
            cand_names += [nfl_full, _abbr(nfl_full)]
        cand_names += [dn, _abbr(dn)]
        hit = None
        for cn in cand_names:
            if norm(cn) in epa_norm:
                hit = epa_norm[norm(cn)]
                break
        if hit:
            epa_out[dn] = hit
    print(f'[DELTA] EPA mapped to {len(epa_out)} DELTA QB/RB players')

    draft_map, college_map, age_map = fetch_draft_and_college(delta_names, meta)
    rb_snap_map = fetch_rb_snap_share(delta_names, meta)

    output = {
        'fetched': datetime.now(timezone.utc).isoformat(),
        'seasons': SEASONS,
        'note':    'Raw stats — PPG calculated client-side per scoring format dropdown',
        'players': players,
        'headshots': headshot_out,
        'qb_roles': qb_roles,
        'teams': team_overrides,
        'epa': epa_out,
        'draft': draft_map,
        'college': college_map,
        'age': age_map,
        'rb_snap': rb_snap_map,
        'rec_pg': rec_pg,
        'ts_delta': ts_delta,
    }
    OUT_FILE.write_text(json.dumps(output, indent=2))
    kb = len(json.dumps(output)) // 1024
    print(f"[DELTA] player-stats.json written ({kb}KB, {len(players)} players)")
    spot_check(players)
    
    # 2. Fetch contracts
    contracts = fetch_contracts(delta_names)
    # Visibility: DELTA players with no active contract upstream (e.g. Stafford
    # June 2026 — extension signed but absent from the nflverse/OTC release).
    # The runtime falls back to the baked CONTRACTS entry for these, silently;
    # this log makes the gap auditable in the Actions output.
    missing_contracts = [n for n in delta_names if n not in contracts]
    print(f'[DELTA] players with NO active upstream contract ({len(missing_contracts)}): {missing_contracts[:15]}')
    
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
