#!/usr/bin/env python3
"""
DELTA — ROOKIE CALIBRATION LAYER (measured). Implements docs/PREREG-ovs-rookie-calibration.md amendment A1.

Per draft range: r = sum w*outcome / sum w*value, w = 0.5^((2026 - t)/8); d = r - 1; se and 95% range from 2,000
resamples within season; d* = d * max(0, 1 - se^2/d^2), applied only where the range excludes 0; factor = 1 + d*.
Two places: draft day (offseason R0 rows) and in season with no game yet (in-season Sb R0 rows, week 9).

    python ovs_rookie_layer.py --nflverse D --rosters D --data NVDATA [--half-tep]
"""
import argparse, json, os, sys, types
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import comps_value_study as C
import comps_draft_drop as DD
import own_value_scale as V
import ovs_in_season as I
import ovs_rookie_calibration as RC

NOW, BOOT, SEED = 2026, 2000, 20261112


def measure(t, b, v, y):
    out = {}
    rng = np.random.default_rng(SEED)
    for k, nm in enumerate(RC.NAMES):
        m = b == k
        tt, vv, yy = t[m], v[m], y[m]
        w = 0.5 ** ((NOW - tt) / V.HALF_LIFE)
        r = (w * yy).sum() / (w * vv).sum(); d = r - 1
        by = [np.where(tt == s)[0] for s in np.unique(tt)]
        ds = []
        for _ in range(BOOT):
            ix = np.concatenate([rng.choice(g, len(g)) for g in by])
            ds.append((w[ix] * yy[ix]).sum() / (w[ix] * vv[ix]).sum() - 1)
        ds = np.array(ds); se = float(ds.std(ddof=1)); lo, hi = np.percentile(ds, [2.5, 97.5])
        excl = bool(lo > 0 or hi < 0)
        dstar = d * max(0.0, 1 - se ** 2 / d ** 2) if (excl and d != 0) else 0.0
        out[nm] = {'rows': int(m.sum()), 'produced_over_value': float(r), 'd': float(d), 'se': float(se),
                   'range_d': [float(lo), float(hi)], 'range_excludes_0': excl, 'factor': float(1 + dstar)}
    return out


def draft_day(a, full_ppr):
    RC.a = a
    S, R, nn, w = RC.frame(full_ppr)
    y = np.nan_to_num(S.FV.values.astype(float))
    v = RC.values(nn, w, y)
    t = S.t.values[R]; b = np.array([RC.band(p) for p in S.pick.values[R]])
    return measure(t, b, v, y[R]), {'rows': int(len(R)), 't_range': [int(t.min()), int(t.max())]}


def in_season(a, full_ppr):
    import new_value_weekly as NVW
    if full_ppr:
        NVW.patch_loads(a.data, NOW)
        C.REPL_N = dict(C.REPL_N_FULL_ADOPTED)
    else:
        C.REPL_N = dict(C.REPL_N_ADOPTED)
    C.HORIZON = 3
    D = a.data
    st, W, Sin, Sb, sk = I.build(os.path.join(D, 'nflv'), os.path.join(D, 'rosters'), os.path.join(D, 'weekly'), 9,
                                 extra=((NOW,) if full_ppr else ()))
    C.POOL_LAG, C.SNAP_FIRST = I.LAG, I.FIRST_Y
    rows = Sb.index[(Sb.kind == 'R0') & Sb.complete & (Sb.t >= I.FIRST_Y + I.LAG) & (Sb.t <= 2022)].values
    pa = DD.neighbours(Sb, rows, 'A', pool_max_t=None)
    y = np.nan_to_num(Sb.FV.values.astype(float)); v, R = [], []
    for r, n in zip(pa['test'], pa['nn'][30]):
        assert (Sb.t.values[n] <= Sb.t.values[r] - I.LAG).all() and Sb.complete.values[n].all()
        ww = 0.5 ** ((Sb.t.values[r] - Sb.t.values[n]) / V.HALF_LIFE); ww /= ww.sum()
        v.append(float((ww * y[n]).sum())); R.append(int(r))
    R = np.array(R); v = np.array(v)
    t = Sb.t.values[R]; b = np.array([RC.band(p) for p in Sb.pick.values[R]])
    return measure(t, b, v, y[R]), {'rows': int(len(R)), 't_range': [int(t.min()), int(t.max())]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True); ap.add_argument('--data', required=True)
    ap.add_argument('--half-tep', action='store_true'); ap.add_argument('--part', choices=['draft', 'inseason'], required=True)
    a = ap.parse_args()
    full = not a.half_tep
    res, info = (draft_day if a.part == 'draft' else in_season)(a, full)
    out = {'prereg': 'docs/PREREG-ovs-rookie-calibration.md A1', 'place': a.part, 'scoring': 'full PPR' if full else 'half PPR + TE premium',
           'lines': C.REPL_N, 'info': info, 'ranges': res}
    name = f"ovs_rookie_layer_{a.part}{'' if full else '_half_tep'}.json"
    json.dump(out, open(os.path.join(HERE, 'out', name), 'w'), indent=1)
    for k, r in res.items():
        print(f"{a.part:9s} {k:7s} rows {r['rows']:4d}  produced/value {r['produced_over_value']:.2f}  range d [{r['range_d'][0]:+.2f},{r['range_d'][1]:+.2f}]  factor {r['factor']:.3f}")


if __name__ == '__main__':
    main()
