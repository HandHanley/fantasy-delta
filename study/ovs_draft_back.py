#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: DRAFT PEDIGREE BACK FOR VETERANS, FADING WITH GAMES. Implements docs/PREREG-ovs-draft-back.md.

Base: the adopted preseason value (offseason features, games out of matching), where draft slot counts 0 from career
year 2 (comps_draft_drop mode A). New: veterans keep the fading draft weight 1.5 x 24 / (career games + 24) at every
career year (the pre-2-Nov rule). Everything else identical.

    python ovs_draft_back.py --nflverse D --rosters D --week1 FILE --counts-only | --crash | --run
"""
import argparse, json, os
import numpy as np
import comps_value_study as C
import comps_draft_drop as DD
import ovs_era as E
import ovs_offseason as O
import own_value_scale as V

LIFT_BAR, ALPHA, ALL_GUARD = 0.02, 0.05, -0.005
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
_M = None                                    # rows decided on: veterans in career year >= 2 among test rows


def nn_for(S, T, cut):
    DD.CUT['A'] = cut
    pc = O.neighbours_off(S, T)
    look = {int(r): nn for r, nn in zip(pc['test'], pc['nn'][30])}
    assert set(look) == set(int(r) for r in T)
    nn_, W_ = [], []
    for r in T:
        nn = look[int(r)]
        assert (S.t.values[nn] <= S.t.values[r] - E.HORIZON).all() and S.key.values[r] not in set(S.key.values[nn])
        w = 0.5 ** ((S.t.values[r] - S.t.values[nn]) / V.HALF_LIFE); nn_.append(nn); W_.append(w / w.sum())
    return nn_, W_


def q(S, pre, p_new, p_old, yt, n_perm=E.N_PERM):
    T = pre['test']; cl = S.key.values[T]; m = _M
    lift, p = C.perm_test(yt[m], p_new[m], p_old[m], cl[m], n_perm)
    lift_all = 1 - C.rmse(p_new, yt) / C.rmse(p_old, yt)
    return {'rows': int(m.sum()), 'rmse_draft_back': C.rmse(p_new[m], yt[m]), 'rmse_base': C.rmse(p_old[m], yt[m]),
            'lift': float(lift), 'p': float(p), 'all_lift': float(lift_all),
            'pass': bool(lift >= LIFT_BAR and p < ALPHA and lift_all >= ALL_GUARD)}


def main():
    global _M
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'week1'): ap.add_argument('--' + k, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--counts-only', action='store_true'); g.add_argument('--crash', action='store_true'); g.add_argument('--run', action='store_true')
    ap.add_argument('--runs', type=int, default=200)
    a = ap.parse_args()
    assert DD.CUT['A'] == 2
    st, S, pre, nn2, W2, nn3, W3, counts = O.setup(a.nflverse, a.rosters, a.week1)
    T = pre['test']; y = S.FV.values.astype(float)
    C.W_V['games'] = 0.0                                                       # adopted preseason: games out
    _M = (S.kind.values[T] == 'V') & (S.cy.values[T] >= 2)
    c = {'test_rows': int(len(T)), 'rows_decided': int(_M.sum()),
         'by_position': {p: int((_M & (S.pos.values[T] == p)).sum()) for p in C.POS}}
    print(json.dumps(c), flush=True)
    if a.counts_only: return
    nnb, Wb = nn_for(S, T, 2)
    nnd, Wd = nn_for(S, T, 99)
    assert DD.vet_weights('A', np.array([24.0]), np.array([5]))[0, 2] == C.W_V['draft'] / 2
    same = [np.array_equal(x, z) for x, z in zip(nnb, nnd)]
    assert all(s for s, m in zip(same, _M) if not m), 'a row outside career year 2+ changed'
    c['decided_rows_with_new_matches'] = int(sum(not s for s, m in zip(same, _M) if m))
    if a.crash:
        E.q1 = lambda S_, pre_, pn, po, yt, n_perm=1000: q(S_, pre_, pn, po, yt, n_perm)
        res = E.crash(S, S, pre, nnb, Wb, nnd, Wd, y, a.runs); res['counts'] = c
        json.dump(res, open(os.path.join(OUT, 'ovs_draft_back_crash.json'), 'w'), indent=1, default=float)
        print(json.dumps({k: v for k, v in res.items() if k != 'counts'}, default=float))
        print('crash tests:', 'PASS' if res['noise']['ok'] and res['planted_0.75']['ok'] else 'FAIL'); return
    po, pn = E.preds(nnb, Wb, y), E.preds(nnd, Wd, y); yt = y[T]; pos = S.pos.values[T]
    res = {'prereg': 'docs/PREREG-ovs-draft-back.md', 'counts': c, 'Q': q(S, pre, pn, po, yt), 'trades': E.q2(S, pre, pn, po, yt),
           'by_position': {p: float(1 - C.rmse(pn[_M & (pos == p)], yt[_M & (pos == p)]) / C.rmse(po[_M & (pos == p)], yt[_M & (pos == p)])) for p in C.POS}}
    few = _M & (S.G.values[T] < 24)
    res['fewer_than_24_career_games'] = {'rows': int(few.sum()), 'lift': float(1 - C.rmse(pn[few], yt[few]) / C.rmse(po[few], yt[few])),
                                         'produced_over_base': float(yt[few].sum() / po[few].sum()),
                                         'produced_over_draft_back': float(yt[few].sum() / pn[few].sum())}
    res['decision'] = 'veterans keep the fading draft weight' if res['Q']['pass'] and res['trades']['guard_ok'] else 'keep draft out from career year 2'
    json.dump(res, open(os.path.join(OUT, 'ovs_draft_back_results.json'), 'w'), indent=1, default=float)
    print(json.dumps({k: res[k] for k in ('Q', 'trades', 'by_position', 'fewer_than_24_career_games', 'decision')}, indent=1, default=float))


if __name__ == '__main__':
    main()
