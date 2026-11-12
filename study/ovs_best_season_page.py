"""Reported only (docs/PREREG-ovs-best-season.md): 2026 week 9 values with best season at the picked weight 3.0. Needs /tmp/ssp/frame_full.pkl and page.pkl (ovs_small_samples_page.py recipe, full W kept). Not a test."""
import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, '/home/claude/fantasy-delta/study')
import comps_value_study as C, own_value_scale as V, ovs_in_season as I, contract_layer as CL, ovs_best_season as B
F = pickle.load(open('frame_full.pkl', 'rb')); Sin, y, W, st = F['Sin'], F['y'], F['W'], F['st']
C.W_V['games'] = 0.0; C.POOL_LAG, C.SNAP_FIRST = I.LAG, I.FIRST_Y
Lf, Lu = I.levels(W)
v = Sin.kind.values == 'V'
Sin['peak'] = np.where(v, np.fmax(Sin['prod'].values, B.peaks(Sin, W, st, Lf)), np.nan)
rows = Sin.index[(Sin.t == 2026) & v].values
def vals(wp):
    g = B.neighbours_peak(Sin, rows, wp); out = {}
    for r, nn in zip(g['test'], g['nn'][30]):
        w = 0.5 ** ((2026 - Sin.t.values[nn]) / V.HALF_LIFE); w /= w.sum(); out[int(r)] = float((w * y[nn]).sum())
    return out
v0, v3 = vals(0.0), vals(3.0)
D0 = pd.read_pickle('page.pkl'); scale = dict(zip(D0.name, D0.today))
T = CL.load('/home/claude/fantasy-delta/data/delta-contracts.json')
f = {r: CL.factor(Sin.name.values[r], T, 2026, 'contract_year')[0] for r in v0}
ref = next(r for r in v0 if Sin.name.values[r] == 'Josh Allen'); mult = scale['Josh Allen'] / (v0[ref] * f[ref])
bad = [Sin.name.values[r] for r in v0 if Sin.name.values[r] in scale and abs(scale[Sin.name.values[r]] - v0[r] * f[r] * mult) > 1e-6]
print('mismatch vs page today:', len(bad), bad[:5])
D = pd.DataFrame({'name': [Sin.name.values[r] for r in v0], 'today': [v0[r] * f[r] * mult for r in v0], 'best': [v3[r] * f[r] * mult for r in v0],
                  'peak': [Sin.peak.values[r] for r in v0], 'prod': [Sin['prod'].values[r] for r in v0]})
allx = dict(zip(D0.name, D0.today))
D['r_today'] = D.today.rank(ascending=False, method='min').astype(int)
# rank of the new value against everyone else's today value (one player changed at a time)
D['r_best'] = [1 + sum(x > b for n, x in allx.items() if n != nm) for nm, b in zip(D.name, D.best)]
show = ['Justin Jefferson', 'Christian McCaffrey', 'Tee Higgins', 'CeeDee Lamb', "Ja'Marr Chase", 'A.J. Brown', 'Jaylen Waddle', 'Davante Adams', 'Saquon Barkley', 'Deshaun Watson', 'Mike Evans']
print(D[D.name.isin(show)].sort_values('today', ascending=False).round(2).to_string(index=False))
