"""Display build (not a test): 2026 week 9 New Value, full PPR, Contract Security. LINES=old|new env var; new = C.REPL_N_FULL_ADOPTED. Writes /tmp/ssp/vals_<lines>.pkl. Then top150_v6_rank.py ranks among site players (/home/claude/vote/pool_all.json)."""
"""Reported only (docs/PREREG-ovs-small-samples.md §4): 2026 week 9, full PPR display build, today vs the mix. Not a test."""
import sys, re, json, types
import numpy as np, pandas as pd
sys.path.insert(0, '/home/claude/fantasy-delta/study')
import comps_value_study as C, comps_draft_drop as DD, own_value_scale as V, ovs_in_season as I, comps_in_season as CI
import injury_weeks as J, ovs_available_ppg as AP, ovs_qb_starts as QS, contract_layer as CL
import ovs_small_samples as SS
SP = '/home/claude/sp'; C.HORIZON = 3
import os
LINES = os.environ.get('LINES', 'old')
if LINES == 'new':
    C.REPL_N = dict(C.REPL_N_FULL_ADOPTED)
print('lines', LINES, C.REPL_N)
_orig_load = C.load
def load_with_2026(nflverse, rosters):
    st, dp, pl = _orig_load(nflverse, rosters)
    wk = pd.read_csv(f'{SP}/weekly/stats_player_week_2026.csv', low_memory=False); wk = wk[wk.season_type == 'REG']
    r26 = pd.read_csv(f'{SP}/rosters2026/roster_2026.csv', low_memory=False, usecols=['gsis_id', 'position']).rename(columns={'gsis_id': 'player_id', 'position': 'rpos'})
    agg = wk.groupby('player_id').agg(player_display_name=('player_display_name', 'last'), position=('position', 'last')).reset_index()
    agg = agg.merge(r26.drop_duplicates('player_id'), on='player_id', how='left')
    agg['position'] = agg.rpos.where(agg.rpos.isin(C.POS), agg.position); agg.loc[agg.position == 'FB', 'position'] = 'RB'
    agg = agg[agg.position.isin(C.POS)]
    add = pd.DataFrame({'player_id': agg.player_id, 'player_display_name': agg.player_display_name, 'season': 2026, 'position': agg.position, 'games': 0.0, 'P': 0.0})
    return pd.concat([st, add.reindex(columns=st.columns)], ignore_index=True), dp, pl
C.load = load_with_2026
_l26 = C.load
def load_full(nflverse, rosters):
    st, dp, pl = _l26(nflverse, rosters); st['P'] = st.fantasy_points_ppr.fillna(0).where(st.season <= 2025, 0.0); return st, dp, pl
C.load = load_full
_ci_load = CI.load
def ci_load_full(*a, **k):
    st, dp, pl, W = _ci_load(*a, **k); W['P'] = np.where(W.g == 1, W.fantasy_points_ppr.fillna(0), 0.0); return st, dp, pl, W
CI.load = ci_load_full
st, W, Sin, Sb, sk = I.build(f'{SP}/nflv', f'{SP}/rosters', f'{SP}/weekly', 9, extra=(2026,))
Lf, Lu = I.levels(W)
a = types.SimpleNamespace(weekly=f'{SP}/weekly', wrost=f'{SP}/wrost', inj=f'{SP}/inj')
AP.prod_available = SS._capturing_prod
SSf, X, parts = QS.build_S(Sin, W, st, Lf, Lu, a, f'{SP}/sched/games.csv', f'{SP}/snaps', f'{SP}/nflv/players.csv')
AP.prod_available = SS._orig_prod
n = SS.CAP['n'].copy(); n[X] = 0
Sin['prod'] = SSf['prod'].values; Sin['kind'] = SSf['kind'].values
C.W_V['games'] = 0.0; C.POOL_LAG, C.SNAP_FIRST = I.LAG, I.FIRST_Y
y = np.nan_to_num(Sin.FV.values.astype(float)); yb = np.nan_to_num(Sb.FV.values.astype(float))
rows = Sin.index[Sin.t == 2026].values
def vals(S, rr, yy):
    pa = DD.neighbours(S, rr, 'A', pool_max_t=None); out = {}
    for r, nn in zip(pa['test'], pa['nn'][30]):
        assert (S.t.values[nn] <= 2022).all() and S.key.values[r] not in set(S.key.values[nn])
        w = 0.5 ** ((2026 - S.t.values[nn]) / V.HALF_LIFE); w /= w.sum(); out[int(r)] = float((w * yy[nn]).sum())
    return out
vin = vals(Sin, rows[~X[rows]], y); vin.update(vals(Sb, rows[X[rows]], yb))
T = CL.load('/home/claude/fantasy-delta/data/delta-contracts.json')
f = {r: CL.factor(Sin.name.values[r], T, 2026, 'contract_year') for r in vin}
val = {r: vin[r] * f[r][0] for r in vin}
top = max(val.values())
out = pd.DataFrame({'r': list(val), 'name': Sin.name.values[list(val)], 'key': Sin.key.values[list(val)], 'pos': Sin.pos.values[list(val)],
                    'games26': [int(Sin.games.values[r]) for r in val], 'rookie': [bool(Sin.rookie_Y.values[r]) for r in val],
                    'age': [round(float(Sin.age.values[r]), 1) for r in val], 'contract': [f[r][1] for r in val],
                    'new_value': [round(10000 * val[r] / top) for r in val]})
out.to_pickle(f'/tmp/ssp/vals_{LINES}.pkl'); print(len(out), out.sort_values('new_value', ascending=False).head(5)[['name', 'new_value']].values.tolist())
