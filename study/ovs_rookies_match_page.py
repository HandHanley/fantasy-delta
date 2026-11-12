"""Reported only (docs/PREREG-ovs-rookies-match-rookies.md §4): 2026 week 9 rookies under today, rookies + second-year, rookies only. Needs /tmp/ssp/frame.pkl and page.pkl from ovs_small_samples_page.py. Not a test."""
import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, '/home/claude/fantasy-delta/study')
import comps_value_study as C, comps_draft_drop as DD, own_value_scale as V, ovs_in_season as I, contract_layer as CL
import ovs_rookies_match as R
F = pickle.load(open('frame.pkl', 'rb')); Sin, y = F['Sin'], F['y']
C.W_V['games'] = 0.0; C.POOL_LAG, C.SNAP_FIRST = I.LAG, I.FIRST_Y
D0 = pd.read_pickle('page.pkl'); top = None
rk = Sin.rookie_Y.values.astype(bool)
rows = Sin.index[(Sin.t == 2026) & rk & (Sin.kind == 'V')].values
def vals(S, rr):
    pa = DD.neighbours(S, rr, 'A', pool_max_t=None); out = {}; nns = {}
    for r, nn in zip(pa['test'], pa['nn'][30]):
        w = 0.5 ** ((2026 - S.t.values[nn]) / V.HALF_LIFE); w /= w.sum(); out[int(r)] = float((w * y[nn]).sum()); nns[int(r)] = (nn, w)
    return out, nns
vt, nt = vals(Sin, rows)
vm, nm = vals(R.restrict(Sin, rk | (Sin.cy.values == 2)), rows)
vo, no = vals(R.restrict(Sin, rk), rows)
T = CL.load('/home/claude/fantasy-delta/data/delta-contracts.json')
# scale: same as page.py (today's top value, contract layer on)
scale = D0.drop_duplicates('name').set_index('name').today
k = [r for r in vt]; ref = k[0]
f = {r: CL.factor(Sin.name.values[r], T, 2026, 'contract_year')[0] for r in k}
mult = scale[Sin.name.values[ref]] / (vt[ref] * f[ref])
bad = [Sin.name.values[r] for r in k if abs(scale[Sin.name.values[r]] - vt[r] * f[r] * mult) > 1e-6]
assert not bad, bad
allv = dict(zip(D0.name, D0.today))
def rank(v, r):
    others = [x for rr, x in allv.items() if rr != Sin.name.values[r]]
    return 1 + sum(x > v for x in others)
out = []
for r in k:
    a, b, c = (vv[r] * f[r] * mult for vv in (vt, vm, vo))
    out.append(dict(name=Sin.name.values[r], pos=Sin.pos.values[r], pick=int(Sin.pick.values[r]) if Sin.pick.values[r] == Sin.pick.values[r] else None,
                    today=round(a), r_today=rank(a, r), rook_soph=round(b), r_rs=rank(b, r), rookies=round(c), r_rook=rank(c, r),
                    soph_in_today=int((Sin.cy.values[nt[r][0]] >= 2).sum())))
D = pd.DataFrame(out).sort_values('today', ascending=False)
D.to_csv('/tmp/ssp/rookies26.csv', index=False)
print(D.head(25).to_string(index=False))
r = int(Sin.index[(Sin.name == 'Omar Cooper Jr.') & (Sin.t == 2026)][0]); nn, w = no[r]
X = Sin.loc[nn, ['name', 't', 'pick', 'prod', 'age']].copy(); X['w'] = w.round(3); X['next3'] = y[nn].round(0)
print('\nCooper rookie-only comparables'); print(X.round(3).to_string(index=False))
print('positive', (y[nn] > 0).mean(), 'median', np.median(y[nn]))
