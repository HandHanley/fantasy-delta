#!/usr/bin/env python3
"""
DELTA — NEW VALUE: ROOKIES KEEP DRAFT VALUE UNTIL 150 OFFENSIVE SNAPS. Implements docs/PREREG-ovs-rookie-snaps.md;
where they disagree, the pre-registration wins.

Reuses ovs_small_samples.py's frame (week 9, rows 2006-2022, In = today's in-season value, Base = this season ignored,
which for a first-year player is his incoming-rookie value, kind R0). Its setup() asserts In reproduces today's value.

    python ovs_rookie_snaps.py --nflverse D --rosters D --weekly D --wrost D --inj D --sched FILE --snaps D
"""
import argparse, json, os
import numpy as np
import comps_value_study as C
import ovs_small_samples as SSm
import rookie_snaps as RS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
MARGIN = 0.005                                       # first-year rows may be at most 0.5% worse than today
N_PERM = 10000


def rmse(p, y):
    return float(np.sqrt(np.mean((p - y) ** 2)))


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'weekly', 'wrost', 'inj', 'sched', 'snaps'): ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    F, S, rows, y, fit, test, n, pin, pbase = SSm.setup(a)          # asserts In == today's value (RMSE 48.4611)
    yr = y[rows]
    rook = S.rookie_Y.values[rows].astype(bool)
    qb = S.pos.values[rows] == 'QB'
    none = F['none'][rows]
    assert (S.kind.values[rows][rook] != 'X').all()
    # today, as the live build values rookies (new_value_weekly.build, `incoming`)
    inc_today = rook & np.where(qb, none, n == 0)
    today = np.where(inc_today, pbase, pin)
    snaps = RS.offense_snaps(a.snaps, os.path.join(a.nflverse, 'players.csv'), SSm.WEEK)
    t = S.t.values[rows]; keys = S.key.values[rows]
    under = np.array([RS.under(snaps, k, tt) for k, tt in zip(keys, t)])
    have = {yy for (_, yy) in snaps}                     # the 2012 file is empty: snap counts start in 2013
    assert set(range(2013, 2023)) <= have and t[test].min() >= 2013, ('snap counts must cover every test season', sorted(have))
    inc_rule = rook & (inc_today | under)
    rule = np.where(inc_rule, pbase, pin)
    m = test & rook
    r_today, r_rule = rmse(today[m], yr[m]), rmse(rule[m], yr[m])
    worse = r_rule / r_today - 1
    lift, p = C.perm_test(yr[m], rule[m], today[m], keys[m], N_PERM)
    res = {'prereg': 'docs/PREREG-ovs-rookie-snaps.md', 'week': SSm.WEEK, 'threshold_snaps': RS.THRESHOLD,
           'decides': {'first_year_rows': int(m.sum()), 'rmse_today': r_today, 'rmse_rule': r_rule,
                       'change': float(-worse), 'allowed_worse': MARGIN, 'pass': bool(worse <= MARGIN)},
           'reported': {
               'all_rows': {'rmse_today': rmse(today[test], yr[test]), 'rmse_rule': rmse(rule[test], yr[test])},
               'first_year_perm': {'lift': float(lift), 'p': float(p)},
               'first_year_rows_under_threshold': int((m & under).sum()),
               'first_year_rows_moved_by_rule': int((m & inc_rule & ~inc_today).sum()),
               'by_position': {q: {'rows': int((m & (S.pos.values[rows] == q)).sum()),
                                   'rmse_today': rmse(today[m & (S.pos.values[rows] == q)], yr[m & (S.pos.values[rows] == q)]),
                                   'rmse_rule': rmse(rule[m & (S.pos.values[rows] == q)], yr[m & (S.pos.values[rows] == q)])}
                               for q in C.POS},
               'produced_over_value': {g: {'rows': int(mm.sum()), 'today': float(yr[mm].sum() / today[mm].sum()),
                                           'rule': float(yr[mm].sum() / rule[mm].sum())}
                                       for g, mm in (('first_year_under_150', m & under & ~inc_today),
                                                     ('first_year_150_plus', m & ~under & ~inc_today),
                                                     ('first_year_all', m))}}}
    json.dump(res, open(os.path.join(OUT, 'ovs_rookie_snaps_results.json'), 'w'), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
