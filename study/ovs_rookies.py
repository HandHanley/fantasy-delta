#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: INCOMING ROOKIES ON DRAFT-SLOT AVERAGES. Implements docs/PREREG-ovs-rookies.md.

Today an incoming rookie (draft-day snapshot) is valued from his 30 closest past rookies by draft slot and age.
The alternative: the plain average of every past player at his position drafted in the same range (picks 1-10,
11-32, 33-64, 65-105, 106+, undrafted) at the same career stage (comps_value_study's B3 bands, unchanged).
Veterans unchanged (the adopted value: era-adjusted, three seasons ahead, offseason changes).

    python ovs_rookies.py --nflverse D --rosters D --week1 FILE --counts-only | --crash | --run
"""
import argparse, json, os
import numpy as np
import comps_value_study as C
import ovs_era as E
import ovs_offseason as O

LIFT_BAR, ALPHA, ALL_GUARD = 0.02, 0.05, -0.005
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')


def setup(nflverse, rosters, week1):
    st, S, pre, nn2, W2, nn3, W3, counts = O.setup(nflverse, rosters, week1)    # adopted value = nn3 / W3
    T = pre['test']; rk = S.kind.values[T] == 'R0'
    nn4, W4 = [], []
    for i, r in enumerate(T):
        if rk[i]:
            m = np.asarray(pre['b3'][i])
            assert (S.t.values[m] <= S.t.values[r] - E.HORIZON).all(), 'band reads an unfinished window'
            assert S.key.values[r] not in set(S.key.values[m]), 'band holds the player himself'
            nn4.append(m); W4.append(np.full(len(m), 1.0 / len(m)))
        else:
            nn4.append(nn3[i]); W4.append(W3[i])
    counts.update({'rookie_rows': int(rk.sum()), 'rookie_players': int(len(set(S.key.values[T][rk]))),
                   'band_size_median': float(np.median([len(pre['b3'][i]) for i in np.where(rk)[0]])),
                   'undrafted_rookie_rows': int(S.undrafted.values[T][rk].astype(bool).sum())})
    return st, S, pre, nn3, W3, nn4, W4, counts


def q(S, pre, p_new, p_old, yt, n_perm=E.N_PERM):
    T = pre['test']; cl = S.key.values[T]; rk = S.kind.values[T] == 'R0'
    lift, p = C.perm_test(yt[rk], p_new[rk], p_old[rk], cl[rk], n_perm)
    lift_all = 1 - C.rmse(p_new, yt) / C.rmse(p_old, yt)
    return {'rookie_rows': int(rk.sum()), 'rmse_bands': C.rmse(p_new[rk], yt[rk]), 'rmse_matches': C.rmse(p_old[rk], yt[rk]),
            'rookie_lift': float(lift), 'rookie_p': float(p), 'all_lift': float(lift_all), 'lift': float(lift),
            'pass': bool(lift >= LIFT_BAR and p < ALPHA and lift_all >= ALL_GUARD)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True); ap.add_argument('--week1', required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--counts-only', action='store_true'); g.add_argument('--crash', action='store_true'); g.add_argument('--run', action='store_true')
    ap.add_argument('--runs', type=int, default=200)
    a = ap.parse_args()
    st, S, pre, nn3, W3, nn4, W4, counts = setup(a.nflverse, a.rosters, a.week1)
    print(json.dumps(counts, indent=1, default=float))
    if a.counts_only: return
    y = S.FV.values.astype(float); T = pre['test']
    if a.crash:
        E.q1 = lambda S_, pre_, pn, po, yt, n_perm=1000: q(S_, pre_, pn, po, yt, n_perm)
        res = E.crash(S, S, pre, nn3, W3, nn4, W4, y, a.runs); res['counts'] = counts
        json.dump(res, open(os.path.join(OUT, 'ovs_rookies_crash.json'), 'w'), indent=1, default=float)
        print('crash tests:', 'PASS' if res['noise']['ok'] and res['planted_0.75']['ok'] else 'FAIL'); return
    po, pn = E.preds(nn3, W3, y), E.preds(nn4, W4, y); yt = y[T]
    res = {'prereg': 'docs/PREREG-ovs-rookies.md', 'counts': counts, 'Q': q(S, pre, pn, po, yt), 'trades': E.q2(S, pre, pn, po, yt)}
    rk = S.kind.values[T] == 'R0'
    res['by_position'] = {p: {'rows': int((rk & (S.pos.values[T] == p)).sum()),
                              'lift': float(1 - C.rmse(pn[rk & (S.pos.values[T] == p)], yt[rk & (S.pos.values[T] == p)])
                                            / C.rmse(po[rk & (S.pos.values[T] == p)], yt[rk & (S.pos.values[T] == p)]))} for p in C.POS}
    blend = 0.5 * (pn + po)
    res['reported_blend_half_half'] = {'rookie_lift_vs_matches': float(1 - C.rmse(blend[rk], yt[rk]) / C.rmse(po[rk], yt[rk]))}
    res['decision'] = 'rookies on draft-slot averages' if res['Q']['pass'] and res['trades']['guard_ok'] else 'keep rookie matches'
    json.dump(res, open(os.path.join(OUT, 'ovs_rookies_results.json'), 'w'), indent=1, default=float)
    print(json.dumps({k: res[k] for k in ('Q', 'trades', 'by_position', 'reported_blend_half_half', 'decision')}, indent=1, default=float))


if __name__ == '__main__':
    main()
