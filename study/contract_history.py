#!/usr/bin/env python3
"""
DELTA — CONTRACT HISTORY, STEP 1: the free part (rookie deals from the draft) and the lookup list. docs/PLAN-contract-history.md.

For every veteran season 2004-2022 (QB/RB/WR/TE with a game; the snapshot entering season t + 1):
  free           drafted 2011 or later and t <= draft year + 1: on the four-year rookie deal for certain (no extension
                 before the third season ends), ending draft year + 3 (DELTA's rookie_rule, data/delta-contracts.json).
  option         a first-rounder drafted 2011+ at t = draft year + 2 or + 3: the fifth-year option decision (one lookup).
  extension      drafted 2011+ at t = draft year + 2: was he extended before season t + 1? (one lookup per player)
  report         everything else: a deal from original reports (veterans, undrafted players, and drafts before 2011,
                 when rookie deal lengths varied).
Relevant = top QB 36 / RB 60 / WR 84 / TE 36 by fantasy points that season.

    python contract_history.py --nflverse D --rosters D --contracts FILE
"""
import argparse, glob, json, os, re
import numpy as np, pandas as pd

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
FIRST, LAST = 2004, 2022
RELEVANT = {'QB': 36, 'RB': 60, 'WR': 84, 'TE': 36}


def norm(s):
    s = re.sub(r"[.'’]", '', str(s).lower()); s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', s); return re.sub(r'[^a-z]', '', s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True); ap.add_argument('--contracts', required=True)
    a = ap.parse_args()
    st = pd.read_csv(os.path.join(a.nflverse, 'player_stats_season.csv'), low_memory=False)
    if 'season_type' in st: st = st[st.season_type == 'REG']
    st = st[st.position.isin(RELEVANT) & (st.games >= 1)].copy()
    st['rank'] = st.groupby(['season', 'position']).fantasy_points.rank(ascending=False, method='min')
    st['relevant'] = [r <= RELEVANT[p] for r, p in zip(st['rank'], st.position)]
    dp = pd.read_csv(os.path.join(a.nflverse, 'draft_picks.csv'), low_memory=False)
    dp = dp[dp.gsis_id.notna()].sort_values(['season', 'pick']).drop_duplicates('gsis_id')
    draft = {g: (int(s), int(r), int(p), t) for g, s, r, p, t in zip(dp.gsis_id, dp.season, dp['round'], dp.pick, dp.team)}
    team = {}
    for f in sorted(glob.glob(os.path.join(a.rosters, 'roster_*.csv'))):
        r = pd.read_csv(f, usecols=['season', 'team', 'gsis_id'], low_memory=False).dropna(subset=['gsis_id'])
        for s, t, g in zip(r.season, r.team, r.gsis_id): team[(g, int(s))] = t
    rows, rookie = [], []
    for g, s, p, n, rel in zip(st.player_id, st.season.astype(int), st.position, st.player_display_name if 'player_display_name' in st else st.player_name, st.relevant):
        if not (FIRST <= s <= LAST): continue
        d = draft.get(g)
        if d and d[0] >= 2011 and s <= d[0] + 1:
            cat = 'free'
            rookie.append({'gsis_id': g, 'name': n, 'pos': p, 'season': s, 'draft_year': d[0], 'round': d[1], 'pick': d[2],
                           'end': d[0] + 3, 'years_left_after_next': d[0] + 3 - (s + 1),
                           'basis': f'Drafted {d[0]}, round {d[1]} (pick {d[2]}): four-year rookie deal, {d[0]}-{d[0] + 3}.',
                           'source': f'https://en.wikipedia.org/wiki/{d[0]}_NFL_draft'})
        elif d and d[0] >= 2011 and d[1] == 1 and s in (d[0] + 2, d[0] + 3): cat = 'option'
        elif d and d[0] >= 2011 and s == d[0] + 2: cat = 'extension'
        else: cat = 'report'
        rows.append({'gsis_id': g, 'name': n, 'pos': p, 'season': s, 'relevant': bool(rel), 'category': cat, 'team': team.get((g, s), '')})
    R = pd.DataFrame(rows); K = pd.DataFrame(rookie)
    R.to_csv(os.path.join(OUT, 'contract_history_rows.csv'), index=False); K.to_csv(os.path.join(OUT, 'contract_history_rookie.csv'), index=False)

    # the job: lookups needed (relevant rows only), counted as player-team stints for report deals
    need = R[R.relevant & (R.category != 'free')].sort_values(['gsis_id', 'season'])
    stints = 0
    for g, x in need[need.category == 'report'].groupby('gsis_id'):
        prev_t, prev_s = None, None
        for t, s in zip(x.team, x.season):
            if t != prev_t or prev_s is None or s - prev_s > 1: stints += 1
            prev_t, prev_s = t, s
    out = {'veteran_seasons': {'all': int(len(R)), 'relevant': int(R.relevant.sum())},
           'by_category_all': R.category.value_counts().to_dict(),
           'by_category_relevant': R[R.relevant].category.value_counts().to_dict(),
           'test_seasons_2013_2022_relevant': R[R.relevant & (R.season >= 2013)].category.value_counts().to_dict(),
           'lookups_relevant': {'option_decisions': int(need[need.category == 'option'].gsis_id.nunique()),
                                'extension_checks': int(need[need.category == 'extension'].gsis_id.nunique()),
                                'report_players': int(need[need.category == 'report'].gsis_id.nunique()),
                                'report_team_stints_(about_one_deal_each)': int(stints)}}

    # check the rookie rule against DELTA's own table (2026 rookie rows)
    T = json.load(open(a.contracts))['players']
    pl = pd.read_csv(os.path.join(a.nflverse, 'players.csv'), low_memory=False)
    by = {}
    for g, n in zip(pl.gsis_id, pl.display_name): by.setdefault(norm(n), set()).add(g)
    agree = disagree = 0; bad = []
    for name, v in T.items():
        if v.get('kind') != 'rookie': continue
        ids = by.get(norm(name), set()); ids = {g for g in ids if g in draft}
        if len(ids) != 1: continue
        d = draft[next(iter(ids))]
        if d[0] + 3 == v.get('end'): agree += 1
        else: disagree += 1; bad.append((name, d[0], v.get('end')))
    out['rookie_rule_vs_delta_table'] = {'agree': agree, 'disagree': disagree, 'disagreements': bad[:10]}
    json.dump(out, open(os.path.join(OUT, 'contract_history_job.json'), 'w'), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))


if __name__ == '__main__':
    main()
