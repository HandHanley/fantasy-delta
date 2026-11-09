#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: ROOKIE QBs WHO SIT. Implements docs/PREREG-ovs-available-ppg.md §7 (measured, deciding nothing).

Week 9, 2013-2022. N = points per available game, no games number (adopted). NQ = the same, but a first-year QB counts
only the games he played that season.

    python ovs_rookie_qb.py --nflverse D --rosters D --weekly D --wrost D --inj D
"""
import argparse, json, os
import numpy as np
import comps_value_study as C
import ovs_in_season as I
import injury_weeks as J
import ovs_available_ppg as AP

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
WEEK = 9


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'weekly', 'wrost', 'inj'): ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    st, W, Sin, Sb, skipped = I.build(a.nflverse, a.rosters, a.weekly, WEEK)
    L_full, L_upto = I.levels(W)
    rows = Sin.index[(Sin.t >= I.TEST[0]) & (Sin.t <= I.TEST[1])].values
    yi = np.nan_to_num(Sin.FV.values.astype(float)); yt = yi[rows]
    A_upto = J.available_weeks(a.weekly, a.wrost, a.inj, WEEK)
    A_full = J.available_weeks(a.weekly, a.wrost, a.inj, 22)
    pN_, _ = AP.prod_available(Sin, W, WEEK, L_full, L_upto, st, A_full, A_upto)
    pQ_, _ = AP.prod_available(Sin, W, WEEK, L_full, L_upto, st, A_full, A_upto, rookie_qb_sits=True)
    rq = Sin.rookie_Y.values & (Sin.pos.values == 'QB')
    diff = ~np.isclose(pN_, pQ_, equal_nan=True)
    assert not (diff & ~rq).any(), 'a row other than a first-year QB changed'
    C.W_V['games'] = 0.0
    SN = Sin.copy(); SN['prod'] = pN_
    SQ = Sin.copy(); SQ['prod'] = pQ_
    ti, nn, w = I.match(SN, rows); pN = AP.paired(rows, ti, nn, w, yi)
    ti, nn, w = I.match(SQ, rows); pQ = AP.paired(rows, ti, nn, w, yi)
    m = rq[rows]
    res = {'amendment': 'docs/PREREG-ovs-available-ppg.md §7', 'rows': int(len(rows)),
           'first_year_qb_rows_all_seasons_changed': int(diff.sum()), 'first_year_qb_test_rows': int(m.sum()),
           'first_year_qb_test_rows_changed': int((diff[rows]).sum()),
           'all_rows': {'rmse_rule': C.rmse(pQ, yt), 'rmse_without': C.rmse(pN, yt), 'change': float(1 - C.rmse(pQ, yt) / C.rmse(pN, yt))},
           'first_year_qbs': {'rmse_rule': C.rmse(pQ[m], yt[m]), 'rmse_without': C.rmse(pN[m], yt[m]),
                              'change': float(1 - C.rmse(pQ[m], yt[m]) / C.rmse(pN[m], yt[m])),
                              'produced_over_rule': float(yt[m].sum() / pQ[m].sum()), 'produced_over_without': float(yt[m].sum() / pN[m].sum())},
           'trades': I.trades(Sin, rows, pQ, pN, yt)}
    json.dump(res, open(os.path.join(OUT, 'ovs_rookie_qb_results.json'), 'w'), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
