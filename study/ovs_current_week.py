"""Display build: Own Value Scale values as of 2026 week 9 (era-adjusted, this season counted, three seasons ahead). Not a test."""
import json, re, sys
import numpy as np, pandas as pd
sys.path.insert(0, '/home/claude/fantasy-delta/study')
import comps_value_study as C, comps_draft_drop as DD, own_value_scale as V, ovs_in_season as I

import argparse
_ap = argparse.ArgumentParser(); _ap.add_argument('--data', required=True, help='folder with nflv/, rosters/, rosters2026/, weekly/, live_values.json')
_ap.add_argument('--scoring', default='half_tep', choices=['half_tep', 'full'], help='full = full PPR, no TE premium (display only; tested on half_tep)')
_ap.add_argument('--live', default='live_values.json', help='live site values file in --data to compare against')
_ap.add_argument('--out', default='values_week9.json')
_ap.add_argument('--no-games', action='store_true', help='games played out of matching (docs/DECISION-no-games-in-matching.md)')
_ap.add_argument('--available-ppg', action='store_true', help='production per available game, no games number (docs/PREREG-ovs-available-ppg.md)')
_ap.add_argument('--rookie-qb-sits', action='store_true', help='with --available-ppg: first-year QBs count only games played (PREREG-ovs-available-ppg.md section 7)')
_ap.add_argument('--show-matches', default='', help='print the 30 matches for this player name (Sin.name)')
_ap.add_argument('--draft-back', action='store_true', help='veterans keep the fading draft weight (docs/PREREG-ovs-draft-back.md)')
_ap.add_argument('--injury-games', action='store_true', help='games so far + weeks out hurt (same doc, section 5); needs wrost/ and inj/ in --data')
_args = _ap.parse_args(); SP = _args.data
C.HORIZON = 3
import glob, os, comps_in_season as CI
# The season file stops at 2025, and CI.load keeps only weekly rows whose (player, season) has a season-file position,
# so 2026 would be dropped silently. Give 2026 rows positions by the same rules (A11/A12): roster position if
# QB/RB/WR/TE, else the weekly file's; FB counts as RB. Only used for this display build; the locked test is untouched.
_orig_load = C.load
def load_with_2026(nflverse, rosters):
    st, dp, pl = _orig_load(nflverse, rosters)
    wk = pd.read_csv(f'{SP}/weekly/stats_player_week_2026.csv', low_memory=False)
    wk = wk[wk.season_type == 'REG']
    r26 = pd.read_csv(f'{SP}/rosters2026/roster_2026.csv', low_memory=False, usecols=['gsis_id', 'position']).rename(columns={'gsis_id': 'player_id', 'position': 'rpos'})
    agg = wk.groupby('player_id').agg(player_display_name=('player_display_name', 'last'), position=('position', 'last')).reset_index()
    agg = agg.merge(r26.drop_duplicates('player_id'), on='player_id', how='left')
    agg['position'] = agg.rpos.where(agg.rpos.isin(C.POS), agg.position)
    agg.loc[agg.position == 'FB', 'position'] = 'RB'
    agg = agg[agg.position.isin(C.POS)]
    add = pd.DataFrame({'player_id': agg.player_id, 'player_display_name': agg.player_display_name, 'season': 2026,
                        'position': agg.position, 'games': 0.0, 'P': 0.0})
    st2 = pd.concat([st, add.reindex(columns=st.columns)], ignore_index=True)
    assert st2[st2.season <= 2025].shape[0] == st.shape[0]
    return st2, dp, pl
C.load = load_with_2026
if _args.scoring == 'full':
    # full PPR, no TE premium: points = fantasy_points_ppr in the season file and the weekly file (both loaders)
    _l26 = C.load
    def load_full(nflverse, rosters):
        st, dp, pl = _l26(nflverse, rosters)
        st['P'] = st.fantasy_points_ppr.fillna(0).where(st.season <= 2025, 0.0)
        return st, dp, pl
    C.load = load_full
    _ci_load = CI.load
    def ci_load_full(*a, **k):
        st, dp, pl, W = _ci_load(*a, **k)
        W['P'] = np.where(W.g == 1, W.fantasy_points_ppr.fillna(0), 0.0)
        return st, dp, pl, W
    CI.load = ci_load_full
st, W, Sin, Sb, sk = I.build(f'{SP}/nflv', f'{SP}/rosters', f'{SP}/weekly', 9, extra=(2026,))
assert (W.season == 2026).sum() > 0, '2026 weekly rows still missing'
print('2026 weekly rows kept:', int((W.season == 2026).sum()), '| 2026 snapshots:', int((Sin.t == 2026).sum()),
      '| with 2026 games:', int(((Sin.t == 2026) & (Sin.games > 0)).sum()))
y = np.nan_to_num(Sin.FV.values.astype(float))
rows = Sin.index[Sin.t == 2026].values
C.POOL_LAG, C.SNAP_FIRST = I.LAG, I.FIRST_Y
if _args.draft_back:
    DD.CUT['A'] = 99
    assert DD.vet_weights('A', np.array([24.0]), np.array([5]))[0, 2] == C.W_V['draft'] / 2
if _args.no_games:
    C.W_V['games'] = 0.0
    assert (DD.vet_weights('A', np.array([0.0, 50.0]), np.array([1, 5]))[:, 4] == 0).all()
if _args.injury_games:
    assert not _args.no_games
    import injury_weeks as J
    _inj = J.injured_weeks(f'{SP}/weekly', f'{SP}/wrost', f'{SP}/inj', 9)
    Sin['games_raw'] = Sin.games
    Sin['games'], _add = J.neutral_games(Sin, _inj, 9)
    Sin['out_hurt'] = _add
if _args.available_ppg:
    assert not (_args.injury_games or _args.no_games)
    import injury_weeks as J, ovs_available_ppg as AP
    _Lf, _Lu = I.levels(W)
    _Au = J.available_weeks(f'{SP}/weekly', f'{SP}/wrost', f'{SP}/inj', 9)
    _Af = J.available_weeks(f'{SP}/weekly', f'{SP}/wrost', f'{SP}/inj', 22)
    Sin['prod'], _lift = AP.prod_available(Sin, W, 9, _Lf, _Lu, st, _Af, _Au, rookie_qb_sits=_args.rookie_qb_sits)
    Sin['games_raw'] = Sin.games
    C.W_V['games'] = 0.0
pa = DD.neighbours(Sin, rows, 'A', pool_max_t=None)
val = {}
for r, nn in zip(pa['test'], pa['nn'][30]):
    assert (Sin.t.values[nn] <= 2022).all() and Sin.complete.values[nn].all()
    assert Sin.key.values[r] not in set(Sin.key.values[nn])
    w = 0.5 ** ((2026 - Sin.t.values[nn]) / V.HALF_LIFE); w /= w.sum()
    val[int(r)] = float((w * y[nn]).sum())
    if _args.show_matches and Sin.name.values[r] == _args.show_matches and Sin.t.values[r] == 2026:
        _cols = [c for c in ('pick', 'draft', 'prod', 'age', 'cy', 'G', 'games') if c in Sin.columns]
        _D = Sin.loc[nn, ['name', 't'] + _cols].copy(); _D['weight'] = w.round(3); _D['next3'] = y[nn].round(1)
        print('MATCHES', _args.show_matches, 'self:', Sin.loc[r, _cols].to_dict(), 'value', round(val[int(r)], 1))
        print(_D.to_string(index=False), flush=True)
top = max(val.values())

def norm(s):
    s = re.sub(r"[.'’]", '', str(s).lower()); s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', s); return re.sub(r'[^a-z]', '', s)
pp = pd.read_csv(f'{SP}/nflv/players.csv', low_memory=False)
alias = {}
for r in pp.itertuples():
    nm = {r.display_name} | {f'{f} {r.last_name}' for f in (r.first_name, r.football_name, r.common_first_name) if isinstance(f, str)}
    alias[r.gsis_id] = {norm(x) for x in nm if isinstance(x, str)}
idx = {}
for r in val:
    for n in {norm(Sin.name.values[r])} | alias.get(Sin.key.values[r], set()):
        idx.setdefault((n, Sin.pos.values[r]), set()).add(r)
L = pd.DataFrame(json.load(open(f'{SP}/{_args.live}'))['players'])
L['r'] = [next(iter(idx[(norm(n), p)])) if len(idx.get((norm(n), p), ())) == 1 else None for n, p in zip(L.n, L.pos)]
prev = pd.read_json(f'{SP}/values_era3.json')[['n', 'r_now']].rename(columns={'r_now': 'r_era'})
first = pd.read_json(f'{SP}/top150.json')[['n', 'r_new']].rename(columns={'r_new': 'r_first'})
M = L[L.r.notna()].copy(); M['r'] = M.r.astype(int)
M['val'] = [round(10000 * val[r] / top) for r in M.r]
M['r_fc'] = M.mkt.rank(ascending=False, method='min').astype(int)
M['r_dv'] = M.mv.rank(ascending=False, method='min').astype(int)
M['r_wk9'] = M.val.rank(ascending=False, method='min').astype(int)
M = M.merge(prev, on='n', how='left').merge(first, on='n', how='left')
M['games26'] = [int((Sin.games_raw if 'games_raw' in Sin else Sin.games).values[r]) for r in M.r]
M['out_hurt26'] = [int(Sin.out_hurt.values[r]) if 'out_hurt' in Sin else 0 for r in M.r]
M['rookie'] = [bool(Sin.rookie_Y.values[r]) for r in M.r]
M['age'] = [round(float(Sin.age.values[r]), 1) for r in M.r]
T = M.sort_values('mkt', ascending=False).head(150)
sp = lambda a, b: round(pd.Series(list(a)).rank().corr(pd.Series(list(b)).rank()), 3)
out = {'matched': int(len(M)), 'site_players': int(len(L)), 'missing': sorted(set(L.n) - set(M.n)),
       'agree_fc_top150': sp(T.mkt, T.val), 'agree_fc_top150_era': sp(T.mkt, T.r_era.max() - T.r_era),
       'top25': [f"{n} ({p})" for n, p in M.sort_values('val', ascending=False).head(25)[['n', 'pos']].values],
       'top50_positions': M.sort_values('val', ascending=False).head(50).pos.value_counts().to_dict(),
       'avg_rank': {p: {'fc': round(T[T.pos == p].r_fc.mean()), 'first': round(T[T.pos == p].r_first.mean()),
                        'era': round(T[T.pos == p].r_era.mean()), 'wk9': round(T[T.pos == p].r_wk9.mean())} for p in ('QB', 'RB', 'WR', 'TE')}}
print(json.dumps(out, indent=1))
show = ['Josh Allen', 'Jahmyr Gibbs', 'Jaxon Smith-Njigba', 'Bijan Robinson', "Ja'Marr Chase", 'Brock Bowers', 'Puka Nacua',
        'Trey McBride', 'Jeremiyah Love', 'Jared Goff', 'Jaxson Dart', 'Bo Nix', 'Baker Mayfield', 'Mike Evans', 'Daniel Jones',
        'Drake Maye', 'Jalen Hurts', 'Lamar Jackson', 'Isaiah Likely']
print(M[M.n.isin(show)].sort_values('r_fc')[['n', 'pos', 'games26', 'r_fc', 'r_first', 'r_era', 'r_wk9']].to_string(index=False))
M.to_json(f'{SP}/{_args.out}', orient='records')
