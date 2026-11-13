#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: DRAFT-DAY ROOKIE VALUES LEARN FROM PAST MISSES. Implements docs/PREREG-ovs-rookie-calibration.md.

Incoming-rookie values (adopted offseason value, kind R0) x a factor per draft range = past (weighted) produced/value
in that range, from classes whose three seasons were complete by then. Decides on classes 2014-2023.

    python ovs_rookie_calibration.py --nflverse D --rosters D --counts | --crash [--runs 200] | --run [--full-ppr]
"""
import argparse, json, os
import numpy as np
import pandas as pd
import comps_value_study as C
import comps_draft_drop as DD
import own_value_scale as V
import ovs_era as E
import pick_values_formats as F

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
EDGES = (12, 32, 64, 100)                 # ranges: 1-12, 13-32, 33-64, 65-100, 101+ (undrafted = 300)
NAMES = ['1-12', '13-32', '33-64', '65-100', '101+']
TEST = (2013, 2022)                       # rows t (classes 2014-2023)
FIRST = 2004                              # first row with a 3-season pool (pool from 2001)
LIFT_BAR, ALPHA = 0.02, 0.05
PLANT = np.array([1.4, 1.4, 1.25, 1.25, 1.0])


def band(pick):
    return int(np.searchsorted(EDGES, pick, side='left'))


def frame(full_ppr):
    if full_ppr:
        F.apply((12, 'SF', 1.0, 0.0)); C.REPL_N = dict(C.REPL_N_FULL_ADOPTED)
    else:
        C.REPL_N = dict(C.REPL_N_ADOPTED)
    st, S, S2, pre, nnA, W, nn2, W2, counts = E.setup(a.nflverse, a.rosters)
    rows = S2.index[(S2.kind == 'R0') & (S2.t >= FIRST) & (S2.t <= TEST[1])].values
    assert S2.complete.values[rows].all()
    pa = DD.neighbours(S2, rows, 'A')
    nn, w = [], []
    for r, n in zip(pa['test'], pa['nn'][30]):
        assert (S2.t.values[n] <= S2.t.values[r] - E.HORIZON).all() and S2.key.values[r] not in set(S2.key.values[n])
        assert S2.complete.values[n].all() and (S2.kind.values[n] == 'R0').all()
        ww = 0.5 ** ((S2.t.values[r] - S2.t.values[n]) / V.HALF_LIFE); nn.append(n); w.append(ww / ww.sum())
    R = pa['test']
    return S2, R, nn, w


def values(nn, w, y):
    return np.array([(ww * y[n]).sum() for n, ww in zip(nn, w)])


def factors(t, b, v, yr):
    """f for each row from rows with t' <= t - 3 in the same range; 1.0 where none exist."""
    f = np.ones(len(t))
    for i in range(len(t)):
        m = (t <= t[i] - E.HORIZON) & (b == b[i])
        if not m.any(): continue
        ww = 0.5 ** ((t[i] - t[m]) / V.HALF_LIFE)
        den = (ww * v[m]).sum()
        f[i] = (ww * yr[m]).sum() / den if den > 0 else 1.0
    return f


def rmse(p, y):
    return float(np.sqrt(np.mean((p - y) ** 2)))


def evaluate(S, R, nn, w, y, n_perm):
    t = S.t.values[R]; b = np.array([band(p) for p in S.pick.values[R]]); yr = y[R]
    v = values(nn, w, y); f = factors(t, b, v, yr); vn = v * f
    test = (t >= TEST[0]) & (t <= TEST[1])
    lift, p = C.perm_test(yr[test], vn[test], v[test], S.key.values[R][test], n_perm)
    return {'rmse_new': rmse(vn[test], yr[test]), 'rmse_today': rmse(v[test], yr[test]), 'lift': float(lift), 'p': float(p),
            'pass': bool(lift >= LIFT_BAR and p < ALPHA)}, v, vn, f, b, t, test


def main():
    global a
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--counts', action='store_true'); g.add_argument('--crash', action='store_true'); g.add_argument('--run', action='store_true')
    ap.add_argument('--runs', type=int, default=200); ap.add_argument('--full-ppr', action='store_true')
    a = ap.parse_args()
    S, R, nn, w = frame(a.full_ppr)
    y = np.nan_to_num(S.FV.values.astype(float))
    t = S.t.values[R]; test = (t >= TEST[0]) & (t <= TEST[1])
    tag = '_full_ppr' if a.full_ppr else ''
    if a.counts:
        b = np.array([band(p) for p in S.pick.values[R]])
        res = {'rows': int(len(R)), 'test_rows': int(test.sum()), 'rows_by_range_test': {NAMES[k]: int(((b == k) & test).sum()) for k in range(5)},
               'lines': C.REPL_N}
        name = f'ovs_rookie_calibration_counts{tag}.json'
    elif a.crash:
        rng = np.random.default_rng(7); res = {}
        grp = pd.DataFrame({'t': S.t.values, 'p': S.pos.values, 'k': S.kind.values}).groupby(['t', 'p', 'k']).groups
        npass = 0
        for i in range(20):
            yn = y.copy()
            for (tt, pp, kk), ix in grp.items():
                if kk != 'R0': continue
                ix = np.array(list(ix)); yn[ix] = y[rng.permutation(ix)]
            r, *_ = evaluate(S, R, nn, w, yn, 1000); npass += r['pass']
        res['noise'] = {'runs': 20, 'passed': int(npass), 'ok': npass <= 1}
        print('noise', res['noise'], flush=True)
        v = values(nn, w, y); b = np.array([band(p) for p in S.pick.values[R]]); yr = y[R]
        resid = yr - v * PLANT[b]; pos = S.pos.values[R]
        rng = np.random.default_rng(75); ok = 0; lifts = []
        for i in range(a.runs):
            e = resid.copy()
            for ps in C.POS:
                m = np.where(pos == ps)[0]; e[m] = resid[rng.permutation(m)]
            truth = np.maximum(0.0, v * PLANT[b] + e)
            f = factors(t, b, v, truth); vn = v * f
            lift, p = C.perm_test(truth[test], vn[test], v[test], S.key.values[R][test], 1000)
            ok += (lift >= LIFT_BAR and p < ALPHA); lifts.append(float(lift))
        res['planted'] = {'runs': a.runs, 'factors': PLANT.tolist(), 'passed': int(ok), 'share': ok / a.runs, 'ok': ok / a.runs >= 0.8,
                          'median_lift': float(np.median(lifts))}
        print('planted', res['planted'], flush=True)
        name = f'ovs_rookie_calibration_crash{tag}.json'
    else:
        r, v, vn, f, b, t_, test_ = evaluate(S, R, nn, w, y, 10000)
        yr = y[R]; pos = S.pos.values[R]
        res = {'prereg': 'docs/PREREG-ovs-rookie-calibration.md', 'scoring': 'full PPR' if a.full_ppr else 'half PPR + TE premium',
               'lines': C.REPL_N, 'decides': r, 'test_rows': int(test_.sum()),
               'by_range': {NAMES[k]: {'rows': int(((b == k) & test_).sum()),
                                       'produced_over_value_today': float(yr[(b == k) & test_].sum() / v[(b == k) & test_].sum()),
                                       'produced_over_value_new': float(yr[(b == k) & test_].sum() / vn[(b == k) & test_].sum()),
                                       'factor_mean': float(f[(b == k) & test_].mean())} for k in range(5)},
               'by_position': {q: {'rows': int(((pos == q) & test_).sum()),
                                   'lift': float(1 - rmse(vn[(pos == q) & test_], yr[(pos == q) & test_]) / rmse(v[(pos == q) & test_], yr[(pos == q) & test_]))}
                               for q in C.POS},
               'factor_by_class': {int(tt) + 1: [round(float(f[(t_ == tt) & (b == k)].mean()), 3) if ((t_ == tt) & (b == k)).any() else None for k in range(5)]
                                   for tt in sorted(set(t_[test_]))}}
        res['decision'] = 'calibrate draft-day rookie values' if r['pass'] else 'no change'
        name = f'ovs_rookie_calibration_results{tag}.json'
    json.dump(res, open(os.path.join(OUT, name), 'w'), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
