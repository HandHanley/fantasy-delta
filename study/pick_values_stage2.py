#!/usr/bin/env python3
"""
DELTA — PICKS, STAGE 2 (after the NFL draft). Implements docs/PLAN-pick-values-now.md §3.

The class's drafted QB/RB/WR/TE rookies get DELTA's incoming-rookie value (draft slot and age; matched with incoming
rookies of earlier classes; outcome = first three seasons, full PPR, the adopted lines), sorted; the k-th best is
slot k. Run now as a check on the 2026 class (t = 2025 snapshots), beside Stage 1's curve.

    python pick_values_stage2.py --nflverse DIR --rosters DIR --cls 2026
"""
import argparse, json, os
import numpy as np
import comps_value_study as C
import comps_draft_drop as DD
import own_value_scale as V
import ovs_era as E
import pick_values_formats as F

FMT = (12, 'SF', 1.0, 0.0)
HERE = os.path.dirname(os.path.abspath(__file__))


def class_values(nflverse, rosters, cls):
    F.apply(FMT)
    C.REPL_N = dict(C.REPL_N_FULL_ADOPTED)
    st, S, S2, pre, nnA, W, nn2, W2, counts = E.setup(nflverse, rosters)
    rows = S2.index[(S2.t == cls - 1) & (S2.kind == 'R0')].values
    pa = DD.neighbours(S2, rows, 'A')
    y = np.nan_to_num(S2.FV.values.astype(float)); out = []
    for r, nn in zip(pa['test'], pa['nn'][30]):
        assert (S2.t.values[nn] <= S2.t.values[r] - E.HORIZON).all() and S2.complete.values[nn].all()
        w = 0.5 ** ((S2.t.values[r] - S2.t.values[nn]) / V.HALF_LIFE); w /= w.sum()
        out.append((S2.name.values[r], S2.pos.values[r], int(S2.pick.values[r]), float((w * y[nn]).sum())))
    return sorted(out, key=lambda x: -x[3])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    ap.add_argument('--cls', type=int, default=2026)
    a = ap.parse_args()
    top = json.load(open(os.path.join(HERE, '..', 'data', 'new-value.json')))['meta']['top_raw']
    st1 = json.load(open(os.path.join(HERE, 'out', 'pick_values_now.json')))['stage1']['new_lines']['per_slot_value']
    vals = class_values(a.nflverse, a.rosters, a.cls)
    rows = [{'slot': k + 1, 'name': n, 'pos': p, 'nfl_pick': pk, 'value': round(10000 * v / top), 'stage1_slot_value': st1[k]}
            for k, (n, p, pk, v) in enumerate(vals[:36])]
    res = {'plan': 'docs/PLAN-pick-values-now.md §3', 'class': a.cls, 'rookies_valued': len(vals), 'top_raw': top, 'slots': rows}
    json.dump(res, open(os.path.join(HERE, 'out', f'pick_values_stage2_{a.cls}.json'), 'w'), indent=1)
    for r in rows: print(r)


if __name__ == '__main__':
    main()
