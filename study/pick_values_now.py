#!/usr/bin/env python3
"""
DELTA — ROOKIE PICKS ON TODAY'S NEW VALUE SCALE. Implements docs/PLAN-pick-values-now.md.

Stage 1: the locked superflex rookie-draft order (pick_values_sf: FFC 1QB ADP re-sorted with the fitted QB boost 1.9,
12-team superflex full PPR), classes 2014-2023, slots 1-36; outcome = FV3 over his first three seasons, full PPR, the
adopted lines; a decreasing isotonic curve over slot. No fairness multiplier (PLAN §2).

    python pick_values_now.py --nflverse DIR --rosters DIR [--newvalue ../data/new-value.json]
"""
import argparse, json, os
import numpy as np
import pandas as pd
import comps_value_study as C
import pick_values as P
import pick_values_formats as F
import pick_values_sf as SF

FMT = (12, 'SF', 1.0, 0.0)
CLASSES = list(range(2014, 2024))
BOOT, SEED = 2000, 20261112
NAMES = [(f'{r} {t}', a, b) for r, base in (('1st', 0), ('2nd', 12), ('3rd', 24))
         for t, a, b in (('Early', base + 1, base + 4), ('Mid', base + 5, base + 8), ('Late', base + 9, base + 12))]


def isotonic_dec(x, y):
    """Pool-adjacent-violators, decreasing in x. Returns the fitted value for each distinct x (sorted)."""
    xs = np.unique(x)
    blocks = [[float(y[x == v].sum()), float((x == v).sum()), [v]] for v in xs]   # sum, count, members
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] / blocks[i][1] < blocks[i + 1][0] / blocks[i + 1][1]:      # violates "decreasing"
            a, b = blocks[i], blocks.pop(i + 1)
            blocks[i] = [a[0] + b[0], a[1] + b[1], a[2] + b[2]]
            i = max(i - 1, 0)
        else:
            i += 1
    out = {}
    for s, n, mem in blocks:
        for v in mem: out[int(v)] = s / n
    return np.array([out[int(v)] for v in xs]), xs


def fv3(st, lines, key, pos, cls):
    v = 0.0
    for j in range(3):
        yr = cls + j
        g = st[(st.season == yr) & (st.position == pos)].P.values
        p = np.sort(g)[::-1]; repl = p[lines[pos] - 1] if len(p) >= lines[pos] else 0.0
        pts = st[(st.player_id == key) & (st.season == yr)].P
        v += C.DISCOUNT ** j * max(0.0, (float(pts.iat[0]) if len(pts) else 0.0) - repl)
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    ap.add_argument('--newvalue', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'new-value.json'))
    a = ap.parse_args()
    B, ff, dp, ids = SF.board()
    b_fit = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'pick_values_sf_fit.json')))['boost']
    assert b_fit == 1.9
    one = SF.build(SF.one_qb(FMT), a.nflverse, a.rosters, B)
    sf = SF.build(FMT, a.nflverse, a.rosters, B)
    slot, E = SF.sf_order(B, one['yb'], {c: b_fit for c in SF.BOARD_CLASSES})
    # reproduction check: the 7 Nov fairness R for this format, from the same order and FV5 outcomes
    pk = SF.picks_from(B, slot, sf['yb'], sf['line'])
    est = P.estimate(pk, sf['vet'], P.Matcher(sf['vet']), pk['y'], sf['vet']['y'], detail=True)
    stored = next(x for x in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'pick_values_sf_results.json')))['formats']
                  if x['key'] == list(FMT))
    assert abs(est['R'] - stored['R']) < 1e-9, ('order/outcomes not reproduced', est['R'], stored['R'])
    st, _, _ = C.load(a.nflverse, a.rosters)                      # full PPR points (F.apply(FMT) is in force)
    assert np.allclose(st.P, st.fantasy_points.fillna(0) + st.receptions)
    m = ~np.isnan(slot) & np.isin(B.cls.values, CLASSES)
    rows = np.where(m)[0]
    line = sf['line']                                             # rookie position line (R0 row's, else the board's)
    out = {}
    for lab, lines in (('new_lines', dict(C.REPL_N_FULL_ADOPTED)), ('old_lines', {'QB': 24, 'RB': 30, 'WR': 42, 'TE': 14})):
        y = np.array([fv3(st, lines, B.gsis.values[j], line[j], int(B.cls.values[j])) for j in rows])
        s = slot[rows].astype(int); cls = B.cls.values[rows]
        fit, xs = isotonic_dec(s, y)
        assert list(xs) == list(range(1, 37))
        raw = [float(y[s == k].mean()) for k in range(1, 37)]
        rng = np.random.default_rng(SEED); bs = []
        by = {c: np.where(cls == c)[0] for c in CLASSES}
        for _ in range(BOOT):
            ix = np.concatenate([rng.choice(v, len(v)) for v in by.values()])
            f_, x_ = isotonic_dec(s[ix], y[ix]); full = np.interp(np.arange(1, 37), x_, f_); bs.append(full)
        bs = np.array(bs)
        names = {}
        for nm, lo, hi in NAMES:
            names[nm] = {'fv3': float(fit[lo - 1:hi].mean()),
                         'range_fv3': [float(np.percentile(bs[:, lo - 1:hi].mean(1), q)) for q in (2.5, 97.5)]}
        out[lab] = {'picks': int(len(y)), 'per_slot_raw_fv3': raw, 'per_slot_curve_fv3': [float(v) for v in fit],
                    'names': names, 'lines': lines,
                    'examples_1_01': [[int(c), B.name.values[j], round(float(v), 1)] for j, c, v, k in zip(rows, cls, y, s) if k == 1]}
    nv = json.load(open(a.newvalue)); top = nv['meta'].get('top_raw')
    res = {'plan': 'docs/PLAN-pick-values-now.md', 'format': '12-team superflex, full PPR', 'boost': b_fit,
           'reproduced_7nov_R': est['R'], 'classes': CLASSES, 'stage1': out, 'top_raw': top}
    if top:
        for lab in out:
            for nm, d in out[lab]['names'].items():
                d['value'] = round(10000 * d['fv3'] / top); d['range'] = [round(10000 * x / top) for x in d['range_fv3']]
            out[lab]['per_slot_value'] = [round(10000 * v / top) for v in out[lab]['per_slot_curve_fv3']]
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'pick_values_now.json')
    json.dump(res, open(p, 'w'), indent=1, default=float)
    print(json.dumps({lab: {nm: (d.get('value'), d.get('range'), round(d['fv3'], 1)) for nm, d in out[lab]['names'].items()} for lab in out}, indent=1))
    print('per slot (new lines):', out['new_lines'].get('per_slot_value'))
    print('1.01s:', out['new_lines']['examples_1_01'])


if __name__ == '__main__':
    main()
