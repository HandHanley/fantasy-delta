#!/usr/bin/env python3
"""
DELTA Player Stats Fetcher — clean rewrite
Uses nflreadpy to fetch NFL weekly stats from nflverse.
Stores raw stat lines in data/player-stats.json.
"""

import json, os, re, sys
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

# ── DATA FLOORS ──────────────────────────────────────────────────────────────
# Every sub-fetch in this file swallows its own exception and returns empty, by
# design: one dead upstream feed should not cost us the other twelve. The cost of
# that design is that a BADLY degraded run still reaches the end, still writes a
# valid-looking JSON file, still exits 0 — and the workflow then commits and
# pushes it to production. The freeze script refuses rather than record something
# plausible; the nightly that FEEDS the freeze should hold the same line.
#
# Floors sit at roughly 75% of observed live counts (11 Aug 2026), so ordinary
# week-to-week drift can never trip them and only real degradation can:
#     players 327 · contracts 394 · draft 372 · universe 409
# Raise these when the universe grows; never lower them to make a red run pass.
MIN_PLAYERS   = 250   # live 327 — matches the freeze pre-flight's own floor
MIN_CONTRACTS = 300   # live 394
MIN_DRAFT     = 250   # live 372 — feeds the rookie draft-capital baseline
MIN_UNIVERSE  = 350   # live 409 — RAW parsed out of delta-engine.js

def die(msg):
    """Abort loudly WITHOUT writing. A missed nightly is recoverable (the site
    keeps serving yesterday's committed data); a nightly that publishes garbage
    is not, because the workflow commits and deploys whatever lands on disk."""
    print(f"\n[DELTA] ABORTED — {msg}", file=sys.stderr)
    print("[DELTA] Nothing was written. Existing data/ files are untouched.", file=sys.stderr)
    sys.exit(1)

# Season window for the stat/trend history. Extended back to 2022 so player pages can
# toggle a multi-season stat line. EPA still looks back one additional year (see fetch_pbp).
SEASONS    = [2022, 2023, 2024, 2025]
OUT_DIR    = Path(__file__).parent.parent / "data"
OUT_FILE   = OUT_DIR / "player-stats.json"
INDEX_HTML = Path(__file__).parent.parent / "delta-engine.js"  # RAW array moved here from index.html

def get_delta_players():
    if not INDEX_HTML.exists():
        # Previously returned ([], set()), which flowed all the way to a written
        # file containing zero players. The universe is the spine of this script:
        # without it there is nothing to match stats against.
        die(f"{INDEX_HTML} not found — cannot read the player universe. "
            "Run from the repo root so scripts/../delta-engine.js resolves.")
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
    # Fumbles lost — a real negative-value signal on player pages (esp. RB/QB ball security).
    fum_col          = col('fumbles_lost_total', 'rushing_fumbles_lost', 'fumbles_lost')
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
              tgt_col, tgt_share_col, air_yds_col, air_yds_share_col, fum_col]:
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
        ('fum_lost',       fum_col),
        ('air_yds',        air_yds_col),
    ]:
        if col_name and col_name in pdf.columns:
            agg_dict[stat_name] = (col_name, 'sum')

    # NOTE: target_share / air_yds_share are intentionally NOT aggregated here.
    # nflverse's per-week shares are team-relative, but averaging them across
    # weeks breaks the sum-to-100 property and inflates part-time / low-volume
    # players. They are computed AFTER the traded-player collapse as season
    # total / team season total (see team_pass_src below).

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

    # Team-season passing denominators for TRUE target/air-yard shares.
    # nflverse's per-week air_yards_share/target_share are team-relative, but
    # averaging them across weeks (old behavior) breaks the sum-to-100 property
    # and badly inflates part-time / low-volume players (2025 LaPorta read 17.5%
    # vs a true 7.5%). Compute the season share as player-season-total /
    # team-season-total instead — sums to 100% across the team and mirrors how
    # rush_share is derived. Denominators come from the weekly pdf (every player,
    # so RBs and non-fantasy receivers are correctly in the pie); the division
    # runs AFTER the traded-player collapse so player totals are full-season.
    team_pass_src = None
    if season_col and team_col and team_col in pdf.columns:
        pass_agg = {}
        if tgt_col and tgt_col in pdf.columns:         pass_agg['team_tgt'] = (tgt_col, 'sum')
        if air_yds_col and air_yds_col in pdf.columns: pass_agg['team_air'] = (air_yds_col, 'sum')
        if pass_agg:
            team_pass_src = pdf.groupby([team_col, season_col]).agg(**pass_agg).reset_index()
            team_pass_src.rename(columns={team_col: 'team', season_col: 'season'}, inplace=True)

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
                                'rush_att','rec','rec_yds','rec_td','targets','air_yds','fum_lost']
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

    # TRUE target/air-yard shares from full-season totals (see team_pass_src).
    # Runs post-collapse so a traded player's summed totals divide by his most
    # recent team's season total — the same edge behavior as rush_share, and far
    # closer than the old weekly mean.
    if team_pass_src is not None:
        result = result.merge(team_pass_src, on=['team', 'season'], how='left')
        if 'targets' in result.columns and 'team_tgt' in result.columns:
            result['target_share'] = result.apply(
                lambda r: round(float(r['targets']) / float(r['team_tgt']), 4)
                if float(r.get('team_tgt') or 0) > 0 else 0.0, axis=1)
        if 'air_yds' in result.columns and 'team_air' in result.columns:
            result['air_yds_share'] = result.apply(
                lambda r: round(float(r['air_yds']) / float(r['team_air']), 4)
                if float(r.get('team_air') or 0) > 0 else 0.0, axis=1)
        result = result.drop(columns=['team_tgt', 'team_air'], errors='ignore')

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
        # (NORMALIZED name, pos) -> set of teams seen; only emit unambiguous ones.
        #
        # The name is normalized because the two feeds spell people differently:
        # the roster feed's full_name carries suffixes ("Deebo Samuel Sr.") while
        # the stats feed's player_name often does not ("Deebo Samuel"). The
        # lookup side keys off the stats name, so an exact tuple match silently
        # dropped every suffixed player and left them on their baked RAW team —
        # invisible, because a miss is indistinguishable from "no override".
        # norm() is the same function match_names() already uses, so both joins
        # now agree on what a name is.
        from collections import defaultdict
        seen = defaultdict(set)
        raw_names = defaultdict(set)
        for _, row in pdf.iterrows():
            key = (norm(row[name_c]), row[pos_c])
            seen[key].add(row[team_c])
            raw_names[key].add(str(row[name_c]))
        out, ambiguous = {}, []
        for key, teams in seen.items():
            if len(teams) == 1:
                out[key] = next(iter(teams))
            else:
                # Either a genuine mid-season move, or two distinct players who
                # normalize to the same key. Both fail CLOSED (baked team kept).
                shown = '/'.join(sorted(raw_names[key]))
                ambiguous.append(f'{shown}/{key[1]}:{sorted(teams)}')
        if ambiguous:
            print(f'[DELTA] roster feed: {len(ambiguous)} ambiguous (name,pos) skipped — {ambiguous[:6]}')
        print(f'[DELTA] roster feed: 2026 skill-position teams for {len(out)} (name,pos) keys')
        return out
    except Exception as e:
        print(f'[DELTA] roster feed unavailable ({e}) — using RAW baked teams')
        return None

SLEEPER_PLAYERS_URL = 'https://api.sleeper.app/v1/players/nfl'

def fetch_sleeper_teams():
    """Current team per skill player from Sleeper's live roster feed.

    Sleeper is the PRIMARY team authority (nflverse is the fallback) because it
    reflects signings within hours, where the nflverse roster release is a
    periodic snapshot that can sit a week or more behind in-season transactions.

    Returns {(normalized_name, position): team} or None if the feed is
    unreachable, in which case the caller falls back to nflverse.

    Two deliberate behaviours:

      * team = null means Sleeper considers the player a free agent. We return
        NO OPINION for those rather than writing 'FA'. Writing 'FA' on a stale
        null would resolve to SYS.FA and silently price the player as a free
        agent — the exact failure mode the 'AZ' bug produced on ten Cardinals.
        A missed release is a stale team; a wrong 'FA' moves scores.

      * A (name, position) pair that maps to more than one team fails CLOSED,
        the same as the nflverse path. That is either two players who normalize
        to one key, or genuinely contradictory data. Neither should overwrite a
        known-good team.

    Note Sleeper lists practice-squad players with a team. That is correct for
    DELTA's purposes: the field answers "whose roster is he on", not "is he
    starting" — snap share already carries the second question.
    """
    import urllib.request
    from collections import defaultdict
    try:
        req = urllib.request.Request(SLEEPER_PLAYERS_URL,
                                     headers={'User-Agent': 'DELTA/1.0 (+fantasydelta.com)'})
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f'[DELTA] Sleeper feed unavailable ({e}) — falling back to nflverse roster feed')
        return None, {}

    if not isinstance(raw, dict) or not raw:
        print('[DELTA] Sleeper feed: empty or unexpected shape — falling back to nflverse')
        return None, {}

    SKILL_POS = {'QB', 'RB', 'WR', 'TE'}
    seen = defaultdict(set)
    raw_names = defaultdict(set)
    free_agents = 0
    injuries = {}
    for _pid, p in raw.items():
        if not isinstance(p, dict):
            continue
        pos = p.get('position')
        if pos not in SKILL_POS:
            continue
        full = p.get('full_name') or ' '.join(
            [x for x in (p.get('first_name'), p.get('last_name')) if x])
        if not full:
            continue

        # Injury status is captured for EVERY skill player, including free
        # agents, and is recorded independently of the team decision below.
        #
        # IMPORTANT: this is a DISPLAY signal only. It never zeroes a
        # projection. NFL rules permit return from injured reserve and
        # designated-to-return is routine, so 'IR' means "out now", not "out
        # for the season". Season-ending calls are made by hand in
        # data/injury-overrides.json. See docs/ACCURACY-LEDGER.md section 6.
        st = (p.get('injury_status') or '').strip()
        if st:
            injuries[(norm(full), pos)] = {
                'status': st,
                'name': full,
                'body_part': (p.get('injury_body_part') or '').strip() or None,
            }

        team = p.get('team')
        if not team:
            free_agents += 1
            continue                      # no opinion — see docstring
        key = (norm(full), pos)
        seen[key].add(team)
        raw_names[key].add(full)

    out, ambiguous = {}, []
    for key, teams in seen.items():
        if len(teams) == 1:
            out[key] = next(iter(teams))
        else:
            ambiguous.append(f"{'/'.join(sorted(raw_names[key]))}/{key[1]}:{sorted(teams)}")
    if ambiguous:
        print(f'[DELTA] Sleeper feed: {len(ambiguous)} ambiguous (name,pos) skipped — {ambiguous[:6]}')
    print(f'[DELTA] Sleeper feed: teams for {len(out)} skill (name,pos) keys '
          f'({free_agents} free agents skipped) · {len(injuries)} carrying an injury status')
    return (out or None), injuries


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

    # Known aliases: DELTA name -> nflverse display name.
    #
    # DIRECT FIRST, ALIAS SECOND. This used to try the alias first, which is fine
    # while every nflverse table agrees on a spelling — and they did, until Gainwell.
    # nflverse is NOT internally consistent about him:
    #     load_player_stats  player_display_name -> 'Kenny Gainwell'
    #     load_players       display_name        -> 'Kenny Gainwell'
    #     load_draft_picks   pfr_player_name     -> 'Kenneth Gainwell'
    #     load_snap_counts   player              -> 'Kenneth Gainwell'
    # DELTA, OTC contracts and the game logs all say 'Kenneth'. Alias-first would fix
    # this join and break the draft/snap joins that use the same alias table; trying
    # the real name first and only falling back to the alias satisfies both, and
    # cannot regress an existing entry (Chig Okonkwo has no direct hit either way).
    ALIASES = {
        'Chigoziem Okonkwo': 'Chig Okonkwo',
        'Kenneth Gainwell':  'Kenny Gainwell',
    }

    matched   = {}
    not_found = []

    for name in delta_names:
        key = norm(name)
        if key not in nfl_norm and name in ALIASES:
            key = norm(ALIASES[name])

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
    # Red zone (inside 20) AND goal line (inside 5) carry/target counts for one season.
    #
    # WHY GOAL LINE SEPARATELY: inside-20 lumps a 19-yard-line target together with a
    # 1-yard-line carry — wildly different TD equity. Goal-line touches are the actual
    # driver of TD upside, and unlike TDs themselves (which are noisy and mean-revert)
    # goal-line usage is STICKY: it is a role a coach assigns. Stored as opportunity
    # data; whether it earns a place in the projection is decided by validation.
    if "yardline_100" not in pdf.columns:
        print(f"[DELTA] No yardline_100 col in {season} PBP — skipping RZ")
        return

    def _counts(frame):
        """(player_tgt, team_tgt, player_car, team_car) for a yardline-filtered frame."""
        rec_name_col = next((c for c in ["receiver_player_name", "receiver_player_display_name"] if c in frame.columns), None)
        if rec_name_col:
            pass_col = next((c for c in ["pass_attempt", "pass"] if c in frame.columns), None)
            tgt_plays = frame[frame[rec_name_col].notna()]
            if pass_col:
                tgt_plays = tgt_plays[tgt_plays[pass_col] == 1]
            p_tgt = tgt_plays.groupby(rec_name_col).size().to_dict()
            t_tgt = tgt_plays.groupby("posteam").size().to_dict()
        else:
            p_tgt, t_tgt = {}, {}
        rush_name_col = next((c for c in ["rusher_player_name", "rusher_player_display_name"] if c in frame.columns), None)
        if rush_name_col:
            rush_col = next((c for c in ["rush_attempt", "rush"] if c in frame.columns), None)
            rush_plays = frame[frame[rush_name_col].notna()]
            if rush_col:
                rush_plays = rush_plays[rush_plays[rush_col] == 1]
            p_car = rush_plays.groupby(rush_name_col).size().to_dict()
            t_car = rush_plays.groupby("posteam").size().to_dict()
        else:
            p_car, t_car = {}, {}
        return p_tgt, t_tgt, p_car, t_car

    player_rz_tgt, team_rz_tgt, player_rz_car, team_rz_car = _counts(pdf[pdf["yardline_100"] <= 20].copy())
    player_gl_tgt, team_gl_tgt, player_gl_car, team_gl_car = _counts(pdf[pdf["yardline_100"] <= 5].copy())

    rz[season] = {
        "player_rz_tgt": player_rz_tgt,
        "player_rz_car": player_rz_car,
        "team_rz_tgt":   team_rz_tgt,
        "team_rz_car":   team_rz_car,
        "player_gl_tgt": player_gl_tgt,
        "player_gl_car": player_gl_car,
        "team_gl_tgt":   team_gl_tgt,
        "team_gl_car":   team_gl_car,
    }
    print(f"[DELTA] RZ {season}: {len(player_rz_tgt)} receivers, {len(player_rz_car)} rushers | "
          f"GL: {len(player_gl_tgt)} receivers, {len(player_gl_car)} rushers")


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
            # Use the SHARED extractor (RZ inside-20 + GL inside-5) so this fallback path
            # can never drift from the primary one.
            _redzone_from_pbp(pdf, season, rz)
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

    def _share(player_dict, team_dict, nfl_name, row):
        """Player's share of his TEAM's red-zone/goal-line opportunities that season.
        Reuses _rz_lookup so the suffix-aware name matching (the 'M.Jr.' fix) applies here
        too — otherwise suffixed players would silently get a 0 share instead of a real one.
        """
        cnt = _rz_lookup(player_dict, nfl_name)
        if cnt is None:
            return None
        team = row.get("team") or row.get("recent_team") or row.get("posteam")
        if not team:
            return None
        tot = team_dict.get(team)
        if not tot:
            return None
        return round(float(cnt) / float(tot), 4)

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
                "fum_lost":      int(r.get("fum_lost", 0) or 0),
                "targets":       int(r.get("targets",  0)),
                "target_share":  round(float(r.get("target_share",  0)), 4),
                "air_yds_share": round(float(r.get("air_yds_share", 0)), 4),
                "rz_targets":    _rz_lookup(rz.get("player_rz_tgt", {}), nfl_name),
                "rz_carries":    _rz_lookup(rz.get("player_rz_car", {}), nfl_name),
                # Goal line (inside 5) — the sharp TD-equity signal. Sticky (a coach-assigned
                # role) where TDs themselves are noisy. Opportunity data only; not scored
                # unless/until validation shows it adds lift beyond production.
                "gl_targets":    _rz_lookup(rz.get("player_gl_tgt", {}), nfl_name),
                "gl_carries":    _rz_lookup(rz.get("player_gl_car", {}), nfl_name),
                # SHARES: 10 RZ targets on a 60-target team is a different player than 10 on
                # a 120-target team. The team totals were already being computed and discarded.
                "rz_tgt_share":  _share(rz.get("player_rz_tgt", {}), rz.get("team_rz_tgt", {}), nfl_name, r),
                "rz_car_share":  _share(rz.get("player_rz_car", {}), rz.get("team_rz_car", {}), nfl_name, r),
                "gl_tgt_share":  _share(rz.get("player_gl_tgt", {}), rz.get("team_gl_tgt", {}), nfl_name, r),
                "gl_car_share":  _share(rz.get("player_gl_car", {}), rz.get("team_gl_car", {}), nfl_name, r),
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
    # Direct spelling first, alias only as a fallback — see the note in match_names().
    # This table is shared by TWO sources that disagree: load_draft_picks says
    # 'Kenneth Gainwell' while load_players says 'Kenny Gainwell'. Alias-first would
    # fix college/age and silently break the draft join for the same player.
    DRAFT_ALIASES = {
        'Chigoziem Okonkwo': 'Chig Okonkwo',
        'Kenneth Gainwell':  'Kenny Gainwell',
    }
    def _match(raw, delta_names):
        rawnorm = {}
        for k in raw:
            rawnorm.setdefault(norm(k), k)
        out = {}
        for dn in delta_names:
            hit = rawnorm.get(norm(dn))
            if hit is None and dn in DRAFT_ALIASES:
                hit = rawnorm.get(norm(DRAFT_ALIASES[dn]))
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

    # ---- COLLEGE + AGE (POSITION-KEYED to defeat same-name collisions) ----
    # load_players() spans all of nflverse history and repeats names across
    # positions — e.g. TWO Lamar Jacksons: QB (born 1997-01-07, age 29.6) and a
    # CB (born 1998-04-13, age 28.3). Keying the maps on NAME ALONE let the last
    # row win, so the DB's birth date clobbered the QB's and DELTA showed Lamar at
    # 28.3. Key on (norm name, position) and match against the DELTA player's own
    # position from `meta`; this mirrors the (name, pos) guard already used for
    # team-matching above. A position miss falls back to the trusted baked age —
    # safe — while a wrong cross-position match (the actual bug) is eliminated.
    try:
        df = nfl.load_players()
        pdf = df.to_pandas() if hasattr(df, 'to_pandas') else df
        cols = set(pdf.columns)
        name_col = next((c for c in ['display_name','full_name','player_name','football_name'] if c in cols), None)
        pos_c    = next((c for c in ['position','pos'] if c in cols), None)
        col_col  = next((c for c in ['college','college_name','college_conference'] if c in cols and 'conference' not in c), None)
        # age (years, 1-decimal) from birth_date if present — same dataset, one pass
        bd_col = next((c for c in ['birth_date','birthdate','birth_year'] if c in cols), None)
        if name_col and pos_c:
            from datetime import date
            today = date.today()
            raw_col = {}   # (norm name, pos) -> college
            raw_age = {}   # (norm name, pos) -> age
            for _, row in pdf.iterrows():
                nm = row.get(name_col)
                ps = row.get(pos_c)
                if not nm or not ps:
                    continue
                key = (norm(nm), str(ps))
                if col_col:
                    cg = row.get(col_col)
                    if cg and str(cg).strip() and str(cg).lower() != 'none':
                        raw_col[key] = str(cg).strip()
                if bd_col:
                    bd = row.get(bd_col)
                    if bd is not None and str(bd).strip() and str(bd).lower() != 'none':
                        try:
                            s = str(bd)[:10]
                            y, m, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
                            age_yrs = (today - date(y, m, d)).days / 365.25
                            if 18 <= age_yrs <= 50:
                                raw_age[key] = round(age_yrs, 1)
                        except (ValueError, TypeError):
                            pass
            for dn in delta_names:
                dpos = meta.get(dn, (None, None))[1]
                if not dpos:
                    continue
                # Direct spelling first, alias as fallback (see _match above). This
                # join reads load_players, which says 'Kenny Gainwell' — so without
                # the fallback he had no college and no age, while the draft join
                # right above resolved him fine under 'Kenneth'.
                k = (norm(dn), dpos)
                if k not in raw_col and k not in raw_age and dn in DRAFT_ALIASES:
                    k = (norm(DRAFT_ALIASES[dn]), dpos)
                if k in raw_col:
                    college_map[dn] = raw_col[k]
                if k in raw_age:
                    age_map[dn] = raw_age[k]
            print(f'[DELTA] college: {len(college_map)} matched · age: {len(age_map)} matched (position-keyed)')
        else:
            print(f'[DELTA] college/age: no name or position column — skipping')
    except Exception as e:
        print(f'[DELTA] college/age fetch failed: {e}')

    return draft_map, college_map, age_map


CONTRACT_OVERRIDES_FILE = Path(__file__).resolve().parent.parent / 'data' / 'contract-overrides.json'

def load_contract_overrides():
    """Read data/contract-overrides.json, a hand-maintained stopgap.

    Shape — a flat map of DELTA player name -> contract fields, plus a free-text
    note recording WHY the entry exists and where the figures came from:

        {
          "Stefon Diggs": {
            "team": "Commanders", "year_signed": 2026, "years": 1,
            "end_year": 2026, "aav": 12.0, "total": 12.0, "guaranteed": 6.0,
            "note": "Signed 5 Aug 2026, per OTC website; absent from the OTC
                     data release as of 8 Aug. Delete once upstream has it."
          }
        }

    Missing file is normal and silent — most of the time there is nothing to
    override. A malformed file is NOT silent: it warns and returns empty, so a
    typo degrades to plain OTC behaviour instead of failing the run.
    """
    if not CONTRACT_OVERRIDES_FILE.exists():
        return {}
    try:
        raw = json.loads(CONTRACT_OVERRIDES_FILE.read_text())
    except Exception as e:
        print(f'[DELTA] contract-overrides.json unreadable ({e}) — ignoring, using OTC only')
        return {}
    if not isinstance(raw, dict):
        print('[DELTA] contract-overrides.json is not an object — ignoring')
        return {}

    REQUIRED = ('team', 'year_signed', 'years', 'aav')
    out = {}
    for name, entry in raw.items():
        if name.startswith('_'):
            continue                                    # allow "_comment" keys
        if not isinstance(entry, dict):
            print(f'[DELTA] contract override for {name!r} is not an object — skipped')
            continue
        missing = [k for k in REQUIRED if entry.get(k) in (None, '')]
        if missing:
            print(f'[DELTA] contract override for {name!r} missing {missing} — skipped')
            continue
        e = {k: v for k, v in entry.items() if k != 'note'}
        if 'end_year' not in e:
            try:
                e['end_year'] = int(e['year_signed']) + int(e['years']) - 1
            except Exception:
                print(f'[DELTA] contract override for {name!r} has bad year fields — skipped')
                continue
        e.setdefault('total', e.get('aav'))
        e.setdefault('guaranteed', 0)
        out[name] = e
    if out:
        print(f'[DELTA] contract-overrides.json: {len(out)} entr(ies) loaded')
    return out


INJURY_LOG_FILE = Path(__file__).resolve().parent.parent / 'data' / 'injury-log.jsonl'

def append_injury_log(injury_status):
    """Append today's injury statuses, one JSON object per line.

    NOTHING READS THIS IN 2026. It exists so that next offseason there is a real
    record of when players went down and came back, to calibrate in-season
    ripple magnitudes against. Building that model from nothing would mean
    waiting another full season; this costs a few KB a night.

    Append-only and one line per day, so it stays diffable and a bad run
    corrupts one line rather than the file.
    """
    if not injury_status:
        return
    try:
        entry = {
            'date': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
            'ts': datetime.now(timezone.utc).isoformat(),
            'players': {k: v.get('status') for k, v in sorted(injury_status.items())},
        }
        INJURY_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(INJURY_LOG_FILE, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(entry) + '\n')
        print(f'[DELTA] injury log: appended {len(entry["players"])} statuses to {INJURY_LOG_FILE.name}')
    except Exception as e:
        # Never fail the run over the observability log.
        print(f'[DELTA] injury log append failed ({e}) — continuing')


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
        
        # Contract-specific aliases: DELTA's spelling -> OTC's spelling.
        # A miss here is expensive and invisible — the player silently falls
        # back to their baked CONTRACTS entry while a perfectly good active
        # contract sits in the feed under a different name. Stafford is the
        # worked example: OTC has "Matt Stafford" with an active 2026 Rams deal
        # (1yr, $55M); DELTA calls him "Matthew Stafford" and matched nothing.
        CONTRACT_ALIASES = {
            "Ja'Marr Chase": "Ja'Marr Chase",
            'Chigoziem Okonkwo': 'Chig Okonkwo',
            'Matthew Stafford': 'Matt Stafford',
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
        
        # ── Hand-maintained overrides ───────────────────────────────────────
        # For the narrow case where a player has demonstrably signed but OTC's
        # dataset has not caught up (Diggs -> WAS, Aug 2026: signing is on OTC's
        # website, absent from their data release).
        #
        # PRECEDENCE: OTC WINS. An override applies only to a player with no
        # active upstream contract, so each entry expires ITSELF the moment the
        # real one lands. That direction matters — the opposite would let a
        # hand-typed figure quietly outlive the truth.
        overrides = load_contract_overrides()
        applied, expired = [], []
        for name, entry in overrides.items():
            if name in contracts:
                expired.append(name)          # OTC has it now; override is dead weight
            elif name in delta_names:
                e = dict(entry)
                e['is_active'] = True
                e['source'] = 'override'
                contracts[name] = e
                applied.append(name)
        if applied:
            print(f'[DELTA] contract overrides applied ({len(applied)}): {sorted(applied)}')
        if expired:
            print(f'[DELTA] contract overrides now redundant — OTC has these, '
                  f'safe to DELETE from data/contract-overrides.json ({len(expired)}): {sorted(expired)}')

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
    # A silent regex miss here (RAW renamed, quoting style changed) would produce a
    # short universe and a short-but-valid output file. Catch it at the source.
    if len(delta_names) < MIN_UNIVERSE:
        die(f"only {len(delta_names)} players parsed from the RAW array (expected ~409). "
            "The RAW block in delta-engine.js may have been renamed or reformatted.")

    agg, headshots, qb_starts = fetch_season_stats()
    matched  = match_names(agg, delta_names, no_data)
    roster_teams = fetch_current_teams()
    sleeper_teams, sleeper_injuries = fetch_sleeper_teams()
    qb_roles = compute_qb_backup_flags(meta, matched, qb_starts, fetch_depth_chart_qbs(), roster_teams)
    # Team overrides for the runtime: only DELTA players the roster feed
    # resolves; RAW's baked team stays the fallback for everyone else.
    # Normalize feed abbreviations to DELTA's convention so we don't churn the
    # team field on pure abbreviation differences (feed JAX/LA/WSH/ARZ vs DELTA
    # JAC/LAR/WAS/ARI) — the runtime AL map aliases these anyway, but writing the
    # canonical form keeps the data clean and the "moved" log honest.
    # Feed abbreviation -> DELTA's convention.
    #
    # 'AZ' was the expensive omission: the 2026 roster feed spells Arizona AZ,
    # TEAM_CANON only knew ARZ, and the engine's AL map only knew ARZ too. So
    # every Cardinal was written as 'AZ', gs('AZ') missed the SYS table, and ten
    # players were scored with SYS.FA — a free agent's system score — while
    # QBQ silently fell back to its 0.85 default. Nothing errored.
    TEAM_CANON = {'JAX': 'JAC', 'LA': 'LAR', 'WSH': 'WAS', 'ARZ': 'ARI', 'AZ': 'ARI'}

    # The 32 codes the engine's SYS/QBQ/COMP_IDX tables are keyed by. Any code
    # outside this set is a code the engine cannot resolve, and an unresolvable
    # code does not fail loudly downstream — it quietly becomes a free agent.
    # So we refuse to emit it at all: the player keeps their baked RAW team,
    # which is stale at worst rather than wrong in a way that moves scores.
    DELTA_TEAMS = {
        'ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE','DAL','DEN','DET','GB',
        'HOU','IND','JAC','KC','LAC','LAR','LV','MIA','MIN','NE','NO','NYG',
        'NYJ','PHI','PIT','SEA','SF','TB','TEN','WAS',
    }
    team_overrides = {}
    injury_status = {}
    unresolved = []
    unknown_codes = {}
    disagreements = []
    src_counts = {'sleeper': 0, 'nflverse': 0}
    if roster_teams or sleeper_teams:
        for dn, nfl_name in matched.items():
            pos = meta.get(dn, (None, None))[1]
            if not pos:
                continue
            # Both feeds are keyed on the SAME normalized (name, position) —
            # see fetch_current_teams() for why normalization is required.
            key = (norm(nfl_name), pos)
            s_t = (sleeper_teams or {}).get(key)
            n_t = (roster_teams or {}).get(key)

            # Record disagreements before choosing. These are informative rather
            # than alarming: usually a transaction nflverse has not picked up
            # yet, occasionally a Sleeper error. Either way it should be visible.
            if s_t and n_t:
                cs, cn = TEAM_CANON.get(s_t, s_t), TEAM_CANON.get(n_t, n_t)
                if cs != cn:
                    disagreements.append(f'{dn}: sleeper={cs} nflverse={cn}')

            # Sleeper wins when it has an opinion; nflverse covers the rest.
            t, source = (s_t, 'sleeper') if s_t else ((n_t, 'nflverse') if n_t else (None, None))
            if t:
                canon = TEAM_CANON.get(t, t)
                if canon in DELTA_TEAMS:
                    team_overrides[dn] = canon
                    src_counts[source] += 1
                else:
                    # Fail CLOSED. See DELTA_TEAMS above for why an unknown code
                    # is worse than a stale one.
                    unknown_codes.setdefault(t, []).append(dn)
            else:
                unresolved.append(f'{dn}/{pos}')
        moved = [f'{dn} {meta[dn][0]}->{t}' for dn, t in team_overrides.items() if dn in meta and meta[dn][0] != t]
        # Print the FULL move list, not a slice. This is the line that tells you
        # whether a real-world signing reached the model, so a truncated tail is
        # exactly the wrong thing to hide (21 moves printing 20 sent us chasing
        # a phantom Diggs bug).
        print(f'[DELTA] team overrides: {len(team_overrides)} resolved '
              f'({src_counts["sleeper"]} from Sleeper, {src_counts["nflverse"]} from nflverse), '
              f'{len(moved)} genuine moves: {moved}')
        if disagreements:
            # Expected during the season; a long list in the offseason means one
            # of the two feeds has gone stale and is worth a look.
            print(f'[DELTA] team source disagreements ({len(disagreements)}, Sleeper wins): '
                  f'{sorted(disagreements)[:25]}')
        # Two distinct ways a DELTA player keeps their baked team. Logged
        # separately because they have different fixes: a stats-unmatched player
        # needs a name alias, a roster-feed miss needs the feed to carry them.
        if unknown_codes:
            # Loud on purpose. This is the alarm that would have caught 'AZ' on
            # day one instead of ten players quietly priced as free agents.
            print('[DELTA] ' + '!' * 68)
            print(f'[DELTA] !! UNKNOWN TEAM CODE(S) FROM ROSTER FEED: {sorted(unknown_codes)}')
            print('[DELTA] !! These do not exist in the engine SYS/QBQ tables. No team')
            print('[DELTA] !! override was written for the players below; they keep their')
            print('[DELTA] !! baked RAW team. Add the mapping to TEAM_CANON (and to AL in')
            print('[DELTA] !! delta-engine.js) to resolve.')
            for code, names in sorted(unknown_codes.items()):
                print(f'[DELTA] !!   {code}: {len(names)} player(s) — {sorted(names)[:15]}')
            print('[DELTA] ' + '!' * 68)
        # Map the Sleeper injury statuses onto DELTA names, using the same
        # normalized (name, position) join the team override uses.
        for dn, nfl_name in matched.items():
            pos = meta.get(dn, (None, None))[1]
            if not pos:
                continue
            rec = (sleeper_injuries or {}).get((norm(nfl_name), pos))
            if rec:
                injury_status[dn] = {'status': rec['status'], 'body_part': rec.get('body_part')}
        if injury_status:
            by_status = {}
            for dn, r in injury_status.items():
                by_status.setdefault(r['status'], []).append(dn)
            print('[DELTA] injury status: ' + ', '.join(
                f'{k}={len(v)}' for k, v in sorted(by_status.items())))
            append_injury_log(injury_status)
        no_stats = sorted(set(delta_names) - set(matched.keys()))
        if unresolved:
            print(f'[DELTA] team overrides: {len(unresolved)} matched players absent from the 2026 roster feed '
                  f'(baked team kept): {sorted(unresolved)[:30]}')
        if no_stats:
            print(f'[DELTA] team overrides: {len(no_stats)} DELTA players have no 2025 stats match, so no team '
                  f'override is possible (baked team kept): {no_stats[:30]}')
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

    # DRAFT CAPITAL IS LOAD-BEARING — promote its failure from a log line to an abort.
    # fetch_draft_and_college() catches its own exception and returns an empty map, so
    # an upstream schema change or outage prints one line and the run continues green.
    # But draft capital is the input to the rookie PPG baseline (median by position x
    # capital tier, 29.9% out-of-sample RMSE improvement over the old flat 8.0). With an
    # empty draft map every prospect silently falls back to that flat value — the exact
    # bug that had 63 of 81 prospects priced as injured veterans. It is invisible in the
    # output: the file is well-formed and full-length, the rookies are just wrong.
    if len(draft_map) < MIN_DRAFT:
        die(f"draft-capital map holds {len(draft_map)} entries (expected ~372). "
            "Rookies would fall back to the flat PPG baseline and price as injured "
            "veterans. Refusing to publish.")

    output = {
        'fetched': datetime.now(timezone.utc).isoformat(),
        'seasons': SEASONS,
        'note':    'Raw stats — PPG calculated client-side per scoring format dropdown',
        'players': players,
        'headshots': headshot_out,
        'qb_roles': qb_roles,
        'teams': team_overrides,
        'injury': injury_status,   # display-only; see docs/ACCURACY-LEDGER.md s.6
        'epa': epa_out,
        'draft': draft_map,
        'college': college_map,
        'age': age_map,
        'rb_snap': rb_snap_map,
        'rec_pg': rec_pg,
        'ts_delta': ts_delta,
    }
    # VALIDATE BEFORE WRITING. spot_check() below is print-only and runs after the
    # write, so it has never been able to stop a bad file from being committed.
    if len(players) < MIN_PLAYERS:
        die(f"only {len(players)} players have stat lines (expected ~327) — the nflverse "
            "weekly-stats fetch returned a partial or empty result.")

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
    # Split the list by whether the player is actually ON a roster. Without this
    # the log mixes two unrelated things: a genuinely unsigned free agent (OTC
    # is CORRECT, nothing to do) and a player who has signed but whose contract
    # has not reached the feed (actionable). Sleeper answers which is which.
    if sleeper_teams:
        rostered, unsigned = [], []
        for n in missing_contracts:
            pos = meta.get(n, (None, None))[1]
            on_roster = bool(pos and sleeper_teams.get((norm(matched.get(n, n)), pos)))
            (rostered if on_roster else unsigned).append(n)
        print(f'[DELTA] players with NO active upstream contract ({len(missing_contracts)}):')
        print(f'[DELTA]   ON a roster per Sleeper — contract genuinely missing, '
              f'consider data/contract-overrides.json ({len(rostered)}): {sorted(rostered)}')
        print(f'[DELTA]   NOT on a roster — unsigned free agents, OTC is correct '
              f'({len(unsigned)}): {sorted(unsigned)[:20]}')
    else:
        print(f'[DELTA] players with NO active upstream contract ({len(missing_contracts)}): {missing_contracts[:15]}')
    
    # Write contracts to separate file
    contracts_output = {
        'fetched': datetime.now(timezone.utc).isoformat(),
        'note': 'Active NFL contracts from nflverse/OTC. end_year = year_signed + years - 1.',
        'contracts': contracts,
    }
    contracts_file = OUT_DIR / "player-contracts.json"
    # Same rule as the stats file. Note this one now matters MORE than it used to:
    # the engine no longer gates contracts behind its baked hand table, so a short
    # contracts file propagates straight to the contract axis for every player in it.
    if len(contracts) < MIN_CONTRACTS:
        die(f"only {len(contracts)} contracts resolved (expected ~394) — the nflverse/OTC "
            "contract feed returned a partial or empty result. player-stats.json was "
            "written; data/ is otherwise unchanged and the previous contracts file stands.")
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
