#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: INJURY-NEUTRAL GAMES IN-SEASON. Implements docs/DECISION-no-games-in-matching.md §5.

Week 9, 2013-2022. Three versions of the in-season value, identical except the games feature:
  G  games so far (the in-season value as adopted)      N  no games (§4)      J  games so far + weeks out hurt

    python ovs_injury_games.py --nflverse D --rosters D --weekly D --wrost D --inj D
"""
import argparse, json, os
import numpy as np
import comps_value_study as C
import ovs_era as E
import ovs_in_season as I
import injury_weeks as J

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
WEEK = 9


def paired(Sx, rows, ti, nn, w, yi):
    pos = {int(r): j for j, r in enumerate(ti)}
    assert set(pos) == set(int(r) for r in rows)
    return I.preds([nn[pos[int(r)]] for r in rows], [w[pos[int(r)]] for r in rows], yi)


def cmp(S, rows, pa, pb, yt):
    lift, p = C.perm_test(yt, pa, pb, S.key.values[rows], E.N_PERM)
    tr = I.trades(S, rows, pa, pb, yt)
    return {'rmse_a': C.rmse(pa, yt), 'rmse_b': C.rmse(pb, yt), 'change': float(lift), 'p_a_better': float(p),
            'trades_a': tr['acc_in_season'], 'trades_b': tr['acc_baseline'], 'trades_diff': tr['diff']}


def ratio(yt, p, m):
    return {'rows': int(m.sum()), 'produced_over_predicted': float(yt[m].sum() / p[m].sum())}


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'weekly', 'wrost', 'inj'): ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    assert C.W_V['games'] == 1.0
    st, Sin, Sb, rows, nni, wi, nnb, wb, ic = I.setup_week(a.nflverse, a.rosters, a.weekly, WEEK)
    yi = np.nan_to_num(Sin.FV.values.astype(float)); yt = yi[rows]
    pG = I.preds(nni, wi, yi)

    inj, parts = J.injured_weeks(a.weekly, a.wrost, a.inj, WEEK, return_parts=True)
    SJ = Sin.copy(); SJ['games'], add = J.neutral_games(Sin, inj, WEEK)
    assert np.array_equal(SJ.key.values, Sin.key.values)
    ti, nn, w = I.match(SJ, rows); pJ = paired(SJ, rows, ti, nn, w, yi)

    C.W_V['games'] = 0.0
    ti, nn, w = I.match(Sin, rows); pN = paired(Sin, rows, ti, nn, w, yi)
    C.W_V['games'] = 1.0

    hurt = add[rows] >= 2
    lowjob = (Sin.games.values[rows] <= 5) & (add[rows] == 0)
    res = {'decision_doc': 'docs/DECISION-no-games-in-matching.md §5', 'week': WEEK, 'rows': int(len(rows)),
           'injury_data': parts, 'rows_with_weeks_out_hurt': int((add[rows] > 0).sum()),
           'J_vs_G': cmp(Sin, rows, pJ, pG, yt), 'J_vs_N': cmp(Sin, rows, pJ, pN, yt),
           'by_position_J_vs_G': {q: float(1 - C.rmse(pJ[m], yt[m]) / C.rmse(pG[m], yt[m]))
                                  for q in C.POS for m in [Sin.pos.values[rows] == q]},
           'out_hurt_2plus': {v: ratio(yt, p, hurt) for v, p in (('G', pG), ('N', pN), ('J', pJ))},
           'low_games_never_hurt': {v: ratio(yt, p, lowjob) for v, p in (('G', pG), ('N', pN), ('J', pJ))}}
    jn = res['J_vs_N']
    res['decision'] = ('no games in-season' if (jn['change'] < 0 and jn['trades_diff'] < 0) else 'injury-neutral games in-season')
    json.dump(res, open(os.path.join(OUT, 'ovs_injury_games_results.json'), 'w'), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
