#!/usr/bin/env python3
"""
DELTA — WHERE SHOULD THE LINES BE? Implements docs/DECISION-replacement-lines.md (a measurement; Steve decides).

Fill 12 teams' lineups with the best available players and count starters by position.
  A  season totals (decides): dedicated slots by position, then flex (RB/WR/TE), then superflex (any)
  B  week by week (reported): weeks 2+, players who played that week, ranked by points per game in earlier weeks
Scoring: half PPR + TE premium (decides), full PPR (reported). Lineups: DELTA's (decides), 2-WR (reported).

    python replacement_lines.py --nflverse D --rosters D --weekly D
"""
import argparse, json, os
import numpy as np
import pandas as pd
import comps_in_season as CI

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
TEAMS = 12
POS = ('QB', 'RB', 'WR', 'TE')
LINEUPS = {'delta': {'QB': 1, 'RB': 2, 'WR': 3, 'TE': 1, 'FLEX': 2, 'SF': 1},
           'two_wr': {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'FLEX': 2, 'SF': 1}}
TODAY = {'QB': 24, 'RB': 30, 'WR': 42, 'TE': 14}
SEASONS = range(2002, 2026)


def fill(df, lineup, score):
    """df: one row per player (pos, score). Returns {pos: starters}, last starter's score by pos, best left out by pos."""
    d = df.sort_values(score, ascending=False)
    taken = np.zeros(len(d), bool); pos = d.pos.values; sc = d[score].values
    for p in POS:
        idx = np.where(pos == p)[0][:lineup[p] * TEAMS]; taken[idx] = True
    flex = np.where(~taken & np.isin(pos, ('RB', 'WR', 'TE')))[0][:lineup['FLEX'] * TEAMS]; taken[flex] = True
    sf = np.where(~taken)[0][:lineup['SF'] * TEAMS]; taken[sf] = True
    n = {p: int((taken & (pos == p)).sum()) for p in POS}
    last = {p: float(sc[taken & (pos == p)].min()) if n[p] else np.nan for p in POS}
    left = {p: float(sc[~taken & (pos == p)].max()) if (~taken & (pos == p)).any() else np.nan for p in POS}
    assert sum(n.values()) == TEAMS * sum(lineup.values())
    return n, last, left


def method_a(st, lineup, col):
    out = {}
    for y in SEASONS:
        s = st[(st.season == y) & st.position.isin(POS)].rename(columns={'position': 'pos'})
        n, last, left = fill(s, lineup, col)
        out[y] = {'starters': n, 'last_starter_points': last, 'best_left_out_points': left}
    return out


def method_b(W, lineup, col):
    out = {}
    for y in SEASONS:
        w = W[(W.season == y) & W.position.isin(POS)]
        wk_max = int(w.week.max()); counts = {p: [] for p in POS}
        played = w[w.g == 1]
        for wk in range(2, wk_max + 1):
            prior = played[played.week < wk].groupby(['player_id', 'position'])[col].mean().rename('ppg').reset_index()
            now = set(played.player_id[played.week == wk])
            d = prior[prior.player_id.isin(now)].rename(columns={'position': 'pos'})
            if len(d) < TEAMS * sum(lineup.values()): continue
            n, _, _ = fill(d, lineup, 'ppg')
            for p in POS: counts[p].append(n[p])
        out[y] = {p: float(np.mean(v)) for p, v in counts.items()}
    return out


def summarize(per_season, key=None, years=SEASONS):
    vals = {p: [] for p in POS}
    for y in years:
        r = per_season[y][key] if key else per_season[y]
        for p in POS: vals[p].append(r[p])
    return {p: round(float(np.mean(v)), 1) for p, v in vals.items()}


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'weekly'): ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    st, dp, pl, W = CI.load(a.nflverse, a.rosters, a.weekly)
    st = st.copy(); st['Pfull'] = st.fantasy_points_ppr.fillna(0)
    W = W.copy(); W['Pfull'] = np.where(W.g == 1, W.fantasy_points_ppr.fillna(0), 0.0)
    res = {'decision_doc': 'docs/DECISION-replacement-lines.md', 'today': TODAY}
    recent = range(2021, 2026)
    for lname, lu in LINEUPS.items():
        for sname, col in (('half_tep', 'P'), ('full_ppr', 'Pfull')):
            A = method_a(st, lu, col)
            B = method_b(W, lu, col)
            res[f'{lname}_{sname}'] = {
                'A_starters_2002_2025': summarize(A, 'starters'), 'A_starters_2021_2025': summarize(A, 'starters', recent),
                'B_starters_2002_2025': summarize(B), 'B_starters_2021_2025': summarize(B, years=recent),
                'A_last_starter_points_2021_2025': summarize(A, 'last_starter_points', recent),
                'A_best_left_out_points_2021_2025': summarize(A, 'best_left_out_points', recent),
                'A_by_season': {int(y): A[y]['starters'] for y in SEASONS}, 'B_by_season': {int(y): B[y] for y in SEASONS}}
            print(lname, sname, {k: v for k, v in res[f'{lname}_{sname}'].items() if 'by_season' not in k}, flush=True)
    json.dump(res, open(os.path.join(OUT, 'replacement_lines_results.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
