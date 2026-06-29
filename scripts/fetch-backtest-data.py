#!/usr/bin/env python3
"""
DELTA Ripple Backtest Data Fetcher
==================================
Produces a STANDALONE calibration dataset for the vacated-opportunity / ripple
backtest. Deliberately separate from player-stats.json:

  · player-stats.json is the LIVE runtime feed — restricted to DELTA's ~409
    universe, 3 seasons. Touching it risks the production engine.
  · This file is CALIBRATION-ONLY — the FULL league, bust-inclusive (every
    skill player who took a snap, plus every drafted skill player even if he
    never earned a touch), across a wide multi-season window.

It serves all three backtest jobs:
  Job 1 (magnitude coefficient)  — cross-sectional opportunity→PPG, all seasons
  Job 2 (allocation rule)        — needs team-by-season to detect departures
  Job 3 (rookie draft prior)     — needs draft capital + bust-inclusive rookie
                                   outcomes (top-tier RBs are sparse, so the
                                   window runs back to 2018 for sample depth)

Output: data/backtest-data.json  (NOT consumed by the runtime — read by the
backtest harness only).

Run in CI where nflverse is reachable; cannot run in the restricted sandbox.
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

# Wide window: 2021-2025 covers Jobs 1 & 2 with large N; back to 2018 gives the
# sparse rookie tiers (top-10 RBs arrive ~1 every 2 yrs) enough sample for Job 3.
SEASONS  = list(range(2018, 2026))
SKILL    = {'QB', 'RB', 'WR', 'TE'}
OUT_DIR  = Path(__file__).parent.parent / "data"
OUT_FILE = OUT_DIR / "backtest-data.json"


def col(pdf, *opts):
    """First matching column name present in the frame (mirrors the live script)."""
    return next((o for o in opts if o in pdf.columns), None)


def fetch_player_seasons():
    """Full-league per-(player, season) opportunity rows for skill positions.
    Mirrors the live script's REG filter, share handling, and multi-team
    collapse so traded players land as one row per season with summed counting
    stats and games-weighted shares."""
    print(f"[BT] Loading weekly player stats {SEASONS[0]}-{SEASONS[-1]} ...")
    df = nfl.load_player_stats(seasons=SEASONS)
    pdf = df.to_pandas() if hasattr(df, 'to_pandas') else df
    if 'season_type' in pdf.columns:
        pdf = pdf[pdf['season_type'] == 'REG'].copy()
    print(f"[BT] Rows: {len(pdf)}")

    name_col   = col(pdf, 'player_display_name')          # FULL names, never player_name (abbrev)
    season_col = col(pdf, 'season', 'year')
    week_col   = col(pdf, 'week', 'game_week')
    pos_col    = col(pdf, 'position', 'pos')
    team_col   = col(pdf, 'team', 'recent_team', 'posteam')
    rush_att_c = col(pdf, 'carries', 'rushing_attempts', 'rush_attempts')
    tgt_c      = col(pdf, 'targets')
    tgt_share_c= col(pdf, 'target_share')
    rec_c      = col(pdf, 'receptions', 'rec')
    rec_yd_c   = col(pdf, 'receiving_yards', 'rec_yards')
    rec_td_c   = col(pdf, 'receiving_tds', 'receiving_touchdowns')
    rush_yd_c  = col(pdf, 'rushing_yards', 'rush_yards')
    rush_td_c  = col(pdf, 'rushing_tds', 'rushing_touchdowns')
    pass_yd_c  = col(pdf, 'passing_yards', 'pass_yards')
    pass_td_c  = col(pdf, 'passing_tds', 'passing_touchdowns')
    pass_int_c = col(pdf, 'passing_interceptions', 'interceptions', 'pass_int')

    if not (name_col and season_col and pos_col and team_col):
        raise ValueError(f"Missing key columns. Have: {list(pdf.columns)[:20]}")

    # Skill positions only
    pdf = pdf[pdf[pos_col].isin(SKILL)].copy()

    # Null-fill numerics
    num_cols = [c for c in [rush_att_c, tgt_c, tgt_share_c, rec_c, rec_yd_c, rec_td_c,
                            rush_yd_c, rush_td_c, pass_yd_c, pass_td_c, pass_int_c] if c]
    for c in num_cols:
        pdf[c] = pdf[c].fillna(0)

    # Aggregate to (name, season, pos, team) — team kept so traded stints split,
    # then collapsed below (same approach as the live fetcher).
    agg_dict = {'games': (week_col, 'nunique'), '_last_week': (week_col, 'max')}
    for nm, c in [('rush_att', rush_att_c), ('targets', tgt_c), ('rec', rec_c),
                  ('rec_yds', rec_yd_c), ('rec_td', rec_td_c), ('rush_yds', rush_yd_c),
                  ('rush_td', rush_td_c), ('pass_yds', pass_yd_c), ('pass_td', pass_td_c),
                  ('pass_int', pass_int_c)]:
        if c:
            agg_dict[nm] = (c, 'sum')
    if tgt_share_c:
        agg_dict['target_share'] = (tgt_share_c, 'mean')   # per-week fraction → mean

    g = pdf.groupby([name_col, season_col, pos_col, team_col]).agg(**agg_dict).reset_index()
    g.rename(columns={name_col: 'name', season_col: 'season', pos_col: 'pos', team_col: 'team'}, inplace=True)

    # rush_share: player carries / team NON-QB carries that season (QB scrambles
    # excluded from the denominator), computed pre-collapse on the weekly frame.
    if rush_att_c:
        non_qb = pdf[pdf[pos_col] != 'QB']
        team_rush = non_qb.groupby([team_col, season_col])[rush_att_c].sum().reset_index()
        team_rush.rename(columns={team_col: 'team', season_col: 'season', rush_att_c: '_team_rush'}, inplace=True)
        g = g.merge(team_rush, on=['team', 'season'], how='left')
        g['rush_share'] = g.apply(
            lambda r: 0.0 if r['pos'] == 'QB'
            else round(float(r['rush_att']) / float(r['_team_rush']), 4) if float(r.get('_team_rush') or 0) > 0 else 0.0,
            axis=1)
    else:
        g['rush_share'] = 0.0

    # Collapse traded player-seasons into one row: counting stats + games SUM,
    # shares games-weighted, team/pos from the most recent stint.
    key = ['name', 'season', 'pos']
    dup = g.duplicated(subset=key, keep=False)
    if dup.any():
        n_tr = g.loc[dup, 'name'].nunique()
        sum_cols = [c for c in ['games','rush_att','targets','rec','rec_yds','rec_td',
                                'rush_yds','rush_td','pass_yds','pass_td','pass_int'] if c in g.columns]
        share_cols = [c for c in ['target_share','rush_share'] if c in g.columns]

        def _collapse(gr):
            gr = gr.sort_values('_last_week')
            out = gr.iloc[-1].copy()
            w = gr['games'].clip(lower=1)
            for c in sum_cols:
                out[c] = gr[c].sum()
            for c in share_cols:
                out[c] = round(float((gr[c] * w).sum() / w.sum()), 4)
            return out

        collapsed = g[dup].groupby(key, as_index=False, group_keys=False).apply(_collapse)
        g = pd.concat([g[~dup], collapsed], ignore_index=True)
        print(f"[BT] Collapsed multi-team seasons for {n_tr} traded players")
    g = g.drop(columns=['_last_week', '_team_rush'], errors='ignore')

    # Reshape to {name: {pos, seasons:{year:{...}}}}
    players = {}
    for _, r in g.iterrows():
        nm = r['name']
        if not nm:
            continue
        gm = int(r.get('games', 0) or 0)
        if gm == 0:
            continue
        opp = int(r.get('targets', 0) or 0) + int(r.get('rush_att', 0) or 0)
        rec = {
            'team':         str(r['team']),
            'games':        gm,
            'targets':      int(r.get('targets', 0) or 0),
            'target_share': round(float(r.get('target_share', 0) or 0), 4),
            'rush_att':     int(r.get('rush_att', 0) or 0),
            'rush_share':   round(float(r.get('rush_share', 0) or 0), 4),
            'opp_pg':       round(opp / gm, 2),                 # (targets + carries) / game
            'rec':          int(r.get('rec', 0) or 0),
            'rec_yds':      int(r.get('rec_yds', 0) or 0),
            'rec_td':       int(r.get('rec_td', 0) or 0),
            'rush_yds':     int(r.get('rush_yds', 0) or 0),
            'rush_td':      int(r.get('rush_td', 0) or 0),
            'pass_yds':     int(r.get('pass_yds', 0) or 0),
            'pass_td':      int(r.get('pass_td', 0) or 0),
            'pass_int':     int(r.get('pass_int', 0) or 0),
        }
        e = players.setdefault(nm, {'pos': str(r['pos']), 'seasons': {}})
        e['seasons'][str(int(r['season']))] = rec
    print(f"[BT] Player-seasons built for {len(players)} skill players")
    return players


def fetch_draft(players):
    """All-history skill-position draft picks: {name: {y, r, p, pos}}. Kept for
    every skill draftee even if they never appear in `players` (true busts) —
    that's the bust-inclusive denominator Job 3 needs."""
    print("[BT] Loading draft picks (all history) ...")
    out = {}
    try:
        df = nfl.load_draft_picks()
        pdf = df.to_pandas() if hasattr(df, 'to_pandas') else df
        name_c = col(pdf, 'pfr_player_name', 'player_name', 'full_name', 'display_name')
        yr_c   = col(pdf, 'season', 'draft_year', 'year')
        rd_c   = col(pdf, 'round')
        pk_c   = col(pdf, 'pick', 'overall', 'selection')
        pos_c  = col(pdf, 'position', 'pos')
        if not (name_c and yr_c and rd_c and pk_c):
            print(f"[BT] draft: missing columns (have {sorted(pdf.columns)[:10]}) — skipping")
            return out
        for _, row in pdf.iterrows():
            nm = row.get(name_c)
            pos = str(row.get(pos_c, '')) if pos_c else ''
            if not nm or (pos_c and pos not in SKILL):
                continue
            try:
                out[nm] = {'y': int(row[yr_c]), 'r': int(row[rd_c]), 'p': int(row[pk_c]), 'pos': pos}
            except (ValueError, TypeError):
                continue
        print(f"[BT] Draft picks: {len(out)} skill players")
    except Exception as e:
        print(f"[BT] draft fetch failed: {e}")
    return out


def sanity(players, draft):
    """CI-visible sanity output so the run can be validated before we trust it."""
    print("\n[BT] === SANITY ===")
    # season coverage
    by_season = {}
    for p in players.values():
        for s in p['seasons']:
            by_season[s] = by_season.get(s, 0) + 1
    print("[BT] skill player-seasons by year:",
          {s: by_season.get(str(s), 0) for s in SEASONS})
    # a traded player's team-by-season (departure detection smoke test)
    for probe in ('A.J. Brown', 'Stefon Diggs', 'Davante Adams'):
        p = players.get(probe)
        if p:
            print(f"[BT] {probe} team-by-season:",
                  {s: d['team'] for s, d in sorted(p['seasons'].items())})
    # rookie top-10 RB opportunity check (validates the ~22 opp/g hypothesis,
    # bust-inclusive: rookie-year = draft year season if present else 0)
    top10_rb = sorted([(d['y'], nm, d['p']) for nm, d in draft.items()
                       if d['pos'] == 'RB' and d['p'] <= 10 and d['y'] >= SEASONS[0]], reverse=True)
    print("[BT] top-10 RB rookie-year opp/game (in-window):")
    for y, nm, pk in top10_rb:
        p = players.get(nm)
        opp = p['seasons'].get(str(y), {}).get('opp_pg', 0.0) if p else 0.0
        print(f"     {y} #{pk:<2} {nm:<22} rookie opp/g = {opp}")


def main():
    print(f"[BT] Starting at {datetime.now(timezone.utc).isoformat()}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    players = fetch_player_seasons()
    draft = fetch_draft(players)
    output = {
        'fetched': datetime.now(timezone.utc).isoformat(),
        'seasons': SEASONS,
        'note': 'CALIBRATION ONLY — full-league bust-inclusive opportunity data + draft picks for the ripple backtest. NOT read by the runtime.',
        'players': players,   # {name: {pos, seasons: {year: {team, opp_pg, target_share, rush_share, ...}}}}
        'draft': draft,       # {name: {y, r, p, pos}}
    }
    OUT_FILE.write_text(json.dumps(output, indent=2))
    kb = len(json.dumps(output)) // 1024
    print(f"[BT] backtest-data.json written ({kb}KB, {len(players)} players, {len(draft)} draft picks)")
    sanity(players, draft)


if __name__ == '__main__':
    main()
