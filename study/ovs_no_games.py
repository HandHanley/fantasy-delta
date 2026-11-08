#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: GAMES PLAYED OUT OF MATCHING. Implements docs/DECISION-no-games-in-matching.md.

Decided by rule (no availability penalty); this measures the cost once and decides nothing. Veteran matching weight on
`games` 1.0 -> 0; everything else unchanged. Preseason (adopted offseason value) and in-season week 9.

    python ovs_no_games.py --nflverse D --rosters D --week1 FILE --weekly D
"""
import argparse, json, os
import numpy as np
import comps_value_study as C
import comps_draft_drop as DD
import ovs_era as E
import ovs_offseason as O
import ovs_in_season as I
import own_value_scale as V

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
MISSED_PRE, MISSED_WK9 = 10, 5          # "missed time": <= 10 games in the snapshot season / <= 5 games by week 9


def games_off():
    C.W_V['games'] = 0.0
    w = DD.vet_weights('A', np.array([0.0, 50.0]), np.array([1, 5]))
    assert (w[:, 4] == 0).all() and (w[:, 0] == C.W_V['prod']).all(), 'games weight not removed'


def compare(S, rows, po, pn, yt, missed, trades):
    cl = S.key.values[rows]; pos = S.pos.values[rows]
    lift, p = C.perm_test(yt, pn, po, cl, E.N_PERM)
    out = {'rows': int(len(rows)), 'rmse_with_games': C.rmse(po, yt), 'rmse_without': C.rmse(pn, yt),
           'change': float(lift), 'p_better': float(p),
           'by_position': {q: float(1 - C.rmse(pn[pos == q], yt[pos == q]) / C.rmse(po[pos == q], yt[pos == q])) for q in C.POS},
           'trades': trades}
    for lab, m in (('missed_time', missed), ('did_not_miss', ~missed & (S.kind.values[rows] == 'V'))):
        out[lab] = {'rows': int(m.sum()), 'produced_over_predicted_with_games': float(yt[m].sum() / po[m].sum()),
                    'produced_over_predicted_without': float(yt[m].sum() / pn[m].sum()),
                    'rmse_change': float(1 - C.rmse(pn[m], yt[m]) / C.rmse(po[m], yt[m]))}
    return out


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'week1', 'weekly'): ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    assert C.W_V['games'] == 1.0

    # ── preseason: the adopted offseason value, then the same matching with games off
    st, S, pre, nn2, W2, nn3, W3, counts = O.setup(a.nflverse, a.rosters, a.week1)
    T = pre['test']; y = S.FV.values.astype(float); yt = y[T]
    po = E.preds(nn3, W3, y)
    games_off()
    pc = O.neighbours_off(S, T)
    look = {int(r): nn for r, nn in zip(pc['test'], pc['nn'][30])}
    assert set(look) == set(int(r) for r in T)
    nn5, W5 = [], []
    for r in T:
        nn = look[int(r)]
        assert (S.t.values[nn] <= S.t.values[r] - E.HORIZON).all() and S.key.values[r] not in set(S.key.values[nn])
        w = 0.5 ** ((S.t.values[r] - S.t.values[nn]) / V.HALF_LIFE); nn5.append(nn); W5.append(w / w.sum())
    pn = E.preds(nn5, W5, y)
    vet = S.kind.values[T] == 'V'
    changed = sum(not np.array_equal(a_, b_) for a_, b_ in zip(nn3, nn5))
    assert all(np.array_equal(a_, b_) for a_, b_, v in zip(nn3, nn5, vet) if not v), 'rookie matches changed'
    missed = vet & (S.games.values[T] <= MISSED_PRE)
    res = {'decision_doc': 'docs/DECISION-no-games-in-matching.md',
           'preseason': compare(S, T, po, pn, yt, missed, E.q2(S, pre, pn, po, yt))}
    res['preseason']['veteran_rows_with_new_matches'] = int(changed)
    print(json.dumps(res, indent=1, default=float), flush=True)

    # ── in-season, week 9: the in-season value with games on, then off
    C.W_V['games'] = 1.0
    st, Sin, Sb, rows, nni, wi, nnb, wb, ic = I.setup_week(a.nflverse, a.rosters, a.weekly, 9)
    yi = np.nan_to_num(Sin.FV.values.astype(float)); yti = yi[rows]
    po9 = I.preds(nni, wi, yi)
    games_off()
    ti, nn9, w9 = I.match(Sin, rows)
    pos9 = {int(r): j for j, r in enumerate(ti)}
    assert set(pos9) == set(int(r) for r in rows)
    pn9 = I.preds([nn9[pos9[int(r)]] for r in rows], [w9[pos9[int(r)]] for r in rows], yi)
    missed9 = (Sin.kind.values[rows] == 'V') & (Sin.games.values[rows] <= MISSED_WK9)
    res['week9'] = compare(Sin, rows, po9, pn9, yti, missed9, I.trades(Sin, rows, pn9, po9, yti))
    json.dump(res, open(os.path.join(OUT, 'ovs_no_games_results.json'), 'w'), indent=1, default=float)
    print(json.dumps(res['week9'], indent=1, default=float))


if __name__ == '__main__':
    main()
