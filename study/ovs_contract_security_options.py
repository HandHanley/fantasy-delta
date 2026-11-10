import sys, json; sys.path.insert(0, '.')
import numpy as np, pandas as pd
import ovs_contract_security as X, ovs_offseason as O, ovs_era as E, ovs_second_contract as SC
st, S, pre, *_ = O.setup('/home/claude/nfl', '/home/claude/nfl/rosters', '/home/claude/nfl/week1.csv')
L = pd.read_csv('out/contract_security_labels.csv')
idx = {(k, int(t)): i for i, (k, t) in enumerate(zip(S.key.values, S.t.values))}
L['row'] = [idx[(g, int(t))] for g, t in zip(L.gsis_id, L.t)]
y = S.FV.values.astype(float); rng = np.random.default_rng(11); out = {}
for name, sel in (('team_signed', L.team_signed & L.group.isin(['0','1','2'])), ('with_rookie_deals', L.group.isin(['0','1','2']))):
    rows = L.row.values[sel.values]; grp = L.group.values[sel.values].astype(int)
    rv, nn_, W_ = SC.base_value(S, rows); assert len(rv) == len(rows)
    v = E.preds(nn_, W_, y); yd = y[rows]; pid = S.key.values[rows]; pos = S.pos.values[rows]; t = S.t.values[rows].astype(int)
    for b in (0.0, 0.10, 0.05):
        h95 = h90 = 0; est = []
        for _ in range(100):
            sh, _t = X.shuffled(grp, None, pos, t, rng)
            ys = yd * np.where(sh == 0, 1 - b, np.where(sh == 2, 1 + b, 1.0))
            r = X.measure(pid, pos, ys, v, None, None, sh, None, rng, n_boot=1000, opp=False)
            r = X.corrected(r, {('points_bump',): X.lean(pid, pos, t, ys, v, None, None, sh, None, rng)[('points_bump',)]})['points_bump']
            h95 += r['excludes_zero_95']; h90 += (r['range_90'][0] > 0 or r['range_90'][1] < 0); est.append(r['estimate'])
        out[f'{name}_{b}'] = {'rows': int(len(rows)), 'excl_95_of_100': int(h95), 'excl_90_of_100': int(h90), 'mean': float(np.mean(est))}
        print(name, b, out[f'{name}_{b}'], flush=True)
json.dump(out, open('/tmp/variants.json', 'w'), indent=1)
