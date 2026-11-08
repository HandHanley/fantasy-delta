#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: TRUE PEERS FOR ELITE PLAYERS. Implements docs/PREREG-ovs-peers.md.

The adopted offseason value (era-adjusted matching, three seasons ahead, offseason changes; ovs_offseason.py) values a
veteran from his 30 closest past matches. For ELITE veterans (top 10% of veterans at his position that season by
era-adjusted production, known at the time) it uses only his 10 closest of those same 30, recency-weighted as before.
Everyone else unchanged.

    python ovs_peers.py --nflverse D --rosters D --week1 FILE --counts-only | --crash | --run
"""
import argparse, json, os
import numpy as np
import comps_value_study as C
import ovs_era as E
import ovs_offseason as O
import own_value_scale as V

K_ELITE, TOP_SHARE = 10, 0.10
LIFT_BAR, ALPHA, ALL_GUARD = 0.02, 0.05, -0.005
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')


def elite_mask(S):
    """Veteran rows in the top 10% of their position-season by era-adjusted production (all snapshots that season)."""
    v = S.kind.values == 'V'; out = np.zeros(len(S), bool)
    for (t, p), g in S[v].groupby(['t', 'pos']):
        cut = np.quantile(g['prod'].values, 1 - TOP_SHARE)
        out[g.index[g['prod'].values >= cut]] = True
    return out


def setup(nflverse, rosters, week1):
    st, S, pre, nn2, W2, nn3, W3, counts = O.setup(nflverse, rosters, week1)        # adopted value = nn3 / W3
    T = pre['test']; el = elite_mask(S); et = el[T]
    nn4, W4 = [], []
    for i, r in enumerate(T):
        if et[i]:
            nn = nn3[i][:K_ELITE]                    # neighbours_off returns matches nearest first
            w = 0.5 ** ((S.t.values[r] - S.t.values[nn]) / V.HALF_LIFE); nn4.append(nn); W4.append(w / w.sum())
        else:
            nn4.append(nn3[i]); W4.append(W3[i])
    counts.update({'elite_rows': int(et.sum()), 'elite_by_position': {p: int((et & (S.pos.values[T] == p)).sum()) for p in C.POS}})
    return st, S, pre, nn3, W3, nn4, W4, el, counts


def q(S, pre, p_new, p_old, yt, n_perm=E.N_PERM, _el=None):
    T = pre['test']; cl = S.key.values[T]; m = _EL[T]
    lift, p = C.perm_test(yt[m], p_new[m], p_old[m], cl[m], n_perm)
    lift_all = 1 - C.rmse(p_new, yt) / C.rmse(p_old, yt)
    return {'elite_rows': int(m.sum()), 'rmse_peers': C.rmse(p_new[m], yt[m]), 'rmse_30': C.rmse(p_old[m], yt[m]),
            'elite_lift': float(lift), 'elite_p': float(p), 'all_lift': float(lift_all), 'lift': float(lift),
            'pass': bool(lift >= LIFT_BAR and p < ALPHA and lift_all >= ALL_GUARD)}


_EL = None


def main():
    global _EL
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True); ap.add_argument('--week1', required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--counts-only', action='store_true'); g.add_argument('--crash', action='store_true'); g.add_argument('--run', action='store_true')
    ap.add_argument('--runs', type=int, default=200)
    a = ap.parse_args()
    st, S, pre, nn3, W3, nn4, W4, _EL, counts = setup(a.nflverse, a.rosters, a.week1)
    print(json.dumps(counts, indent=1, default=float))
    if a.counts_only: return
    y = S.FV.values.astype(float); T = pre['test']
    if a.crash:
        E.q1 = lambda S_, pre_, pn, po, yt, n_perm=1000: q(S_, pre_, pn, po, yt, n_perm)
        res = E.crash(S, S, pre, nn3, W3, nn4, W4, y, a.runs); res['counts'] = counts
        json.dump(res, open(os.path.join(OUT, 'ovs_peers_crash.json'), 'w'), indent=1, default=float)
        print('crash tests:', 'PASS' if res['noise']['ok'] and res['planted_0.75']['ok'] else 'FAIL'); return
    po, pn = E.preds(nn3, W3, y), E.preds(nn4, W4, y); yt = y[T]; m = _EL[T]
    res = {'prereg': 'docs/PREREG-ovs-peers.md', 'counts': counts, 'Q': q(S, pre, pn, po, yt), 'trades': E.q2(S, pre, pn, po, yt)}
    res['by_position_elite'] = {p: float(1 - C.rmse(pn[m & (S.pos.values[T] == p)], yt[m & (S.pos.values[T] == p)])
                                         / C.rmse(po[m & (S.pos.values[T] == p)], yt[m & (S.pos.values[T] == p)])) for p in C.POS}
    res['elite_calibration'] = {'produced_over_predicted_30': float(yt[m].sum() / po[m].sum()),
                                'produced_over_predicted_peers': float(yt[m].sum() / pn[m].sum())}
    res['decision'] = 'elite players on 10 closest peers' if res['Q']['pass'] and res['trades']['guard_ok'] else 'keep 30 matches'
    json.dump(res, open(os.path.join(OUT, 'ovs_peers_results.json'), 'w'), indent=1, default=float)
    print(json.dumps({k: res[k] for k in ('Q', 'trades', 'by_position_elite', 'elite_calibration', 'decision')}, indent=1, default=float))


if __name__ == '__main__':
    main()
