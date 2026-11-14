#!/usr/bin/env python3
"""
DELTA — NEW VALUE: NO ONE MATCH CARRIES A PLAYER. Implements docs/PREREG-ovs-one-match.md; where they disagree, the
pre-registration wins.

Today a player's value is the recency-weighted average of what his 30 matches went on to score. The rule tested here:
before averaging, any match who scored more than the player's THIRD-best match counts as if he had scored the
third-best match's total ("capped at the third-best"). A long shot whose value is one Brock Purdy among 27 zeros falls;
a star whose matches are all stars barely moves.

Reuses ovs_small_samples.py's frame (week 9, test rows 2013-2022). "Today" is the live build: in-season value, with
first-year players who have no game (QBs: no real game) or are under 150 offensive snaps on their incoming-rookie value.

    python ovs_one_match.py --mode crash|run --nflverse D --rosters D --weekly D --wrost D --inj D --sched FILE --snaps D
"""
import argparse, json, os
import numpy as np
import pandas as pd
import comps_value_study as C
import ovs_small_samples as SSm
import rookie_snaps as RS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
CAP_AT = 3                      # pre-registered: capped at the third-best match
REPORT_CAPS = (2, 4, 5)         # reported only, deciding nothing
BAR, ALPHA, N_PERM = 0.02, 0.05, 10000
MOVED = 0.20                    # amendment A1: decided on rows whose value the cap lowers by 20%+ (values only)
GUARD = 0.005                   # amendment A1: all rows may be at most 0.5% worse


def rmse(p, y):
    return float(np.sqrt(np.mean((p - y) ** 2)))


def capped_preds(nn, Wt, y, k):
    out = np.empty(len(nn))
    for i, (n, w) in enumerate(zip(nn, Wt)):
        o = y[n]
        c = np.sort(o)[-k] if len(o) >= k else o.max()
        out[i] = (w * np.minimum(o, c)).sum()
    return out


def frame(a):
    F, S, rows, y, fit, test, n, pin, pbase = SSm.setup(a)          # asserts In == the adopted value (RMSE 48.4611)
    rook = S.rookie_Y.values[rows].astype(bool)
    qb = S.pos.values[rows] == 'QB'
    inc_today = rook & np.where(qb, F['none'][rows], n == 0)
    snaps = RS.offense_snaps(a.snaps, os.path.join(a.nflverse, 'players.csv'), SSm.WEEK)
    t = S.t.values[rows]; keys = S.key.values[rows]
    under = np.array([RS.under(snaps, k, tt) for k, tt in zip(keys, t)])
    on_draft = rook & (inc_today | under)                            # the live build's rookie rule
    return dict(F=F, S=S, rows=rows, y=y, test=test, on_draft=on_draft, keys=keys, pos=S.pos.values[rows], t=t,
                rook=rook, pick=np.exp(S.draft.values[rows]))


def values(G, y, k=None):
    F, d = G['F'], G['on_draft']
    if k is None:
        pin, pb = np.array([(w * y[n]).sum() for n, w in zip(F['nnI'], F['wI'])]), np.array([(w * y[n]).sum() for n, w in zip(F['nnB'], F['wB'])])
    else:
        pin, pb = capped_preds(F['nnI'], F['wI'], y, k), capped_preds(F['nnB'], F['wB'], y, k)
    return np.where(d, pb, pin)


def decide_all(G, today, new, truth, n_perm=N_PERM):
    m = G['test']
    r0, r1 = rmse(today[m], truth[m]), rmse(new[m], truth[m])
    lift, p = C.perm_test(truth[m], new[m], today[m], G['keys'][m], n_perm)
    return {'rows': int(m.sum()), 'rmse_today': r0, 'rmse_capped': r1, 'lift': float(lift), 'p': float(p),
            'pass': bool(lift >= BAR and p < ALPHA)}


decide = decide_all                 # the original rule (section 2), kept for the record and the first crash test


def moved_rows(today, new):
    """Rows whose value the cap lowers by 20% or more. Values only: no outcome is read."""
    return (today > 0) & ((today - new) >= MOVED * today)


def decide_a1(G, today, new, truth, n_perm=N_PERM):
    """Amendment A1 (Steve, 13 Nov): 2% / p<0.05 on test rows the cap moves 20%+; all test rows at most 0.5% worse."""
    mv = G['test'] & moved_rows(today, new); m = G['test']
    r0, r1 = rmse(today[mv], truth[mv]), rmse(new[mv], truth[mv])
    lift, p = C.perm_test(truth[mv], new[mv], today[mv], G['keys'][mv], n_perm)
    a0, a1 = rmse(today[m], truth[m]), rmse(new[m], truth[m])
    worse = a1 / a0 - 1
    return {'moved_rows': int(mv.sum()), 'rmse_today': r0, 'rmse_capped': r1, 'lift': float(lift), 'p': float(p),
            'all_rows': int(m.sum()), 'all_rmse_today': a0, 'all_rmse_capped': a1, 'all_rows_worse_by': float(worse),
            'pass': bool(lift >= BAR and p < ALPHA and worse <= GUARD)}


def crash_a1_noise(G, runs=20):
    """A1's noise check: outcomes shuffled within position and season; values and the moved rows rebuilt from them."""
    y, rows, S = G['y'], G['rows'], G['S']
    rng = np.random.default_rng(7)
    grp = pd.DataFrame({'p': S.pos.values, 't': S.t.values}).groupby(['p', 't']).groups
    npass = 0; lifts = []
    for i in range(runs):
        yn = y.copy()
        for g in grp.values():
            g = np.array(list(g)); yn[g] = y[rng.permutation(g)]
        r = decide_a1(G, values(G, yn), values(G, yn, CAP_AT), yn[rows], n_perm=1000)
        npass += r['pass']; lifts.append(r['lift'])
    res = {'noise_a1': {'runs': runs, 'passed': int(npass), 'ok': npass <= 1, 'median_lift': float(np.median(lifts))}}
    print(res, flush=True)
    return res


def crash(G, runs=200, noise_runs=20):
    y, rows = G['y'], G['rows']; S = G['S']
    res = {}
    rng = np.random.default_rng(7)
    grp = pd.DataFrame({'p': S.pos.values, 't': S.t.values}).groupby(['p', 't']).groups
    npass = 0; lifts = []
    for i in range(noise_runs):
        yn = y.copy()
        for g in grp.values():
            g = np.array(list(g)); yn[g] = y[rng.permutation(g)]
        r = decide(G, values(G, yn), values(G, yn, CAP_AT), yn[rows], n_perm=1000)
        npass += r['pass']; lifts.append(r['lift'])
    res['noise'] = {'runs': noise_runs, 'passed': int(npass), 'ok': npass <= 1, 'median_lift': float(np.median(lifts))}
    print('noise', res['noise'], flush=True)
    today, cap = values(G, y), values(G, y, CAP_AT)
    resid = y[rows] - cap
    rng = np.random.default_rng(75); ok = 0; lifts = []
    for i in range(runs):
        e = resid.copy()
        for ps in C.POS:
            m = np.where(G['pos'] == ps)[0]; e[m] = resid[rng.permutation(m)]
        truth = np.maximum(0.0, cap + e)
        r = decide(G, today, cap, truth, n_perm=1000)
        ok += r['pass']; lifts.append(r['lift'])
    res['planted'] = {'runs': runs, 'passed': int(ok), 'share': ok / runs, 'ok': ok / runs >= 0.80,
                      'median_lift': float(np.median(lifts))}
    print('planted', res['planted'], flush=True)
    return res


def run(G):
    y, rows, m = G['y'], G['rows'], G['test']
    yr = y[rows]
    today, cap = values(G, y), values(G, y, CAP_AT)
    res = {'prereg': 'docs/PREREG-ovs-one-match.md', 'week': SSm.WEEK, 'cap_at': CAP_AT, 'decides_a1': decide_a1(G, today, cap, yr)}
    rep = {'original_rule_all_rows': decide_all(G, today, cap, yr)}
    rep['other_caps'] = {}
    for k in REPORT_CAPS:
        v = values(G, y, k)
        mv = m & moved_rows(today, v)
        rep['other_caps'][k] = {'all_rows_lift': float(1 - rmse(v[m], yr[m]) / rmse(today[m], yr[m])), 'moved_rows': int(mv.sum()),
                                'moved_rows_lift': float(1 - rmse(v[mv], yr[mv]) / rmse(today[mv], yr[mv]))}
    rep['by_position'] = {q: {'rows': int((m & (G['pos'] == q)).sum()),
                              'rmse_today': rmse(today[m & (G['pos'] == q)], yr[m & (G['pos'] == q)]),
                              'rmse_capped': rmse(cap[m & (G['pos'] == q)], yr[m & (G['pos'] == q)])} for q in C.POS}
    rep['spearman'] = {'today': float(pd.Series(today[m]).corr(pd.Series(yr[m]), method='spearman')),
                       'capped': float(pd.Series(cap[m]).corr(pd.Series(yr[m]), method='spearman'))}
    # produced / value by today's value band (test rows), today and capped
    q = pd.qcut(pd.Series(today[m]).rank(method='first'), 5, labels=['bottom fifth', 'fourth', 'middle', 'second', 'top fifth'])
    rep['produced_over_value_by_band'] = {str(b): {'rows': int((q == b).sum()),
                                                   'today': float(yr[m][(q == b).values].sum() / today[m][(q == b).values].sum()),
                                                   'capped': float(yr[m][(q == b).values].sum() / cap[m][(q == b).values].sum())}
                                          for b in q.cat.categories}
    late = m & G['rook'] & G['on_draft'] & (G['pick'] > 100)
    rep['late_round_rookies_on_draft_value'] = {'rows': int(late.sum()), 'produced_over_value_today': float(yr[late].sum() / today[late].sum()),
                                                'produced_over_value_capped': float(yr[late].sum() / cap[late].sum()),
                                                'rmse_today': rmse(today[late], yr[late]), 'rmse_capped': rmse(cap[late], yr[late])}
    res['reported'] = rep
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('crash', 'crash_a1', 'run'), required=True)
    for k in ('nflverse', 'rosters', 'weekly', 'wrost', 'inj', 'sched', 'snaps'): ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    G = frame(a)
    res = crash(G) if a.mode == 'crash' else crash_a1_noise(G) if a.mode == 'crash_a1' else run(G)
    fn = os.path.join(OUT, f'ovs_one_match_{a.mode}.json')
    json.dump(res, open(fn, 'w'), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
