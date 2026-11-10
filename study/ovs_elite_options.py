"""Power of an alternative to docs/PREREG-ovs-elite.md (shuffled outcome-to-value ratios only; reveals nothing real).
Stretch test: slope of delivered on value within a position (1 = right spread; above 1 = values too bunched, so the
top is shortchanged). Planted: the same top-3 x 1.25 as the elite crash test."""
import sys, json, numpy as np
sys.path.insert(0, '.')
import ovs_offseason as O, ovs_era as E, ovs_second_contract as SC, ovs_elite as X
from ovs_contract_security import Boot
st, S, pre, *_ = O.setup(*sys.argv[1:4])
test = np.asarray(pre['test'], int); M = test[(S.kind.values[test] == 'V') & S.complete.values[test].astype(bool)]
rows, nn_, W_ = SC.base_value(S, M); y_all = S.FV.values.astype(float); v = E.preds(nn_, W_, y_all); y = y_all[rows]
pid, pos, t = S.key.values[rows], S.pos.values[rows], S.t.values[rows].astype(int); rk = X.ranks(v, pos, t)
rng = np.random.default_rng(5)

def slope(B, y, v, m):
    """Weighted least-squares slope per bootstrap, rows in m (weights = resample counts)."""
    ix = np.where(m)[0]; W = B.Wt[:, B.ix[ix]]; yy, vv = y[ix], v[ix]
    sw = W.sum(1); mv = (W * vv).sum(1) / sw; my = (W * yy).sum(1) / sw
    return (W * (vv - mv[:, None]) * (yy - my[:, None])).sum(1) / (W * (vv - mv[:, None]) ** 2).sum(1)

out = {}
for scope in ('ranks_1_24', 'all_rows'):
    for p in ('TE', 'WR'):
        m = (pos == p) & ((rk <= 24) if scope == 'ranks_1_24' else True)
        for b in (0.0, 0.25):
            hit = 0; est = []
            for _ in range(100):
                ys = X.null_world(y, v, pos, t, rk, rng); ys = np.where(rk <= 3, ys * (1 + b), ys)
                B = Boot(pid, 500, rng); s = slope(B, ys, v, m)
                B0 = Boot(pid, 0, rng); ln = np.mean([slope(B0, X.null_world(ys, v, pos, t, rk, rng), v, m)[0] for _ in range(50)])
                s = s - ln + 1; lo, hi = np.quantile(s[1:], [.025, .975]); hit += (lo > 1 or hi < 1); est.append(s[0])
            out[f'{scope}_{p}_{b}'] = {'rows': int(m.sum()), 'excluded_one_of_100': int(hit), 'mean': float(np.mean(est))}
            print(scope, p, b, out[f'{scope}_{p}_{b}'], flush=True)
json.dump(out, open('out/ovs_elite_power_options.json', 'w'), indent=1)
