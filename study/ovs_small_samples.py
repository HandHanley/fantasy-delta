#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: DON'T OVERREACT TO A FEW GAMES. Implements docs/PREREG-ovs-small-samples.md; where they
disagree, the pre-registration wins.

Week 9. Two values per row, both already built:
  In    today's adopted in-season value (ovs_qb_starts.build_S: per available game, §7, §8, no games number)
  Base  this season ignored (frame Sb, same matching); a rookie's is his incoming-rookie value (kind R0)
n = the games this season's production rests on (prod_available's own denominator, captured, not re-derived).
Mix = n/(n+K) * In + K/(n+K) * Base. K picked from {1,2,4,8,16} on t = 2006-2012; tested on 2013-2022 vs In.

    python ovs_small_samples.py --nflverse D --rosters D --weekly D --wrost D --inj D --sched FILE --snaps D --counts
    python ovs_small_samples.py ... --crash [--runs 200]      # before lock
    python ovs_small_samples.py ... --run                     # once, after lock
"""
import argparse, json, os, pickle
import numpy as np
import pandas as pd
import comps_value_study as C
import ovs_in_season as I
import injury_weeks as J
import ovs_available_ppg as AP
import ovs_qb_starts as QS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
WEEK = 9
FIT = (2006, 2012)
TEST = (2013, 2022)
GRID = (1, 2, 4, 8, 16)
LIFT_BAR, ALPHA, TRADE_GUARD = 0.02, 0.05, -1.0
PLANT_K = 4
CACHE = '/tmp/ovs_small_samples_frame.pkl'
EXPECT_TEST_RMSE_IN = 48.461133390000334       # ovs_qb_starts.py re-run 12 Nov on the same data folder (all_rows.rmse_rule);
                                               # the 9 Nov results file reads 48.460984 (data refresh, 0.0003%)


# ── n: prod_available's own denominator for season Y, captured while build_S runs ────────────────
def _make_prod_with_n():
    """AP.prod_available's own source with one change: it also returns aY, the denominator it used for season Y.
    Built from the source text so n can't drift from the production it describes; every edit asserts one match."""
    import inspect, textwrap
    src = textwrap.dedent(inspect.getsource(_orig_prod))
    edits = [("def prod_available(", "def prod_available_n("),
             ("    out = []\n", "    out = []; NS = []\n"),
             ("        out.append(v if kin == 'V' else np.nan)\n", "        out.append(v if kin == 'V' else np.nan); NS.append(aY)\n"),
             ("    return np.array(out, float), lifted\n", "    return np.array(out, float), lifted, np.array(NS, float)\n")]
    for old, new in edits:
        c = src.count(old); assert c == 1, (old, c); src = src.replace(old, new)
    ns = dict(vars(AP)); exec(src, ns)
    return ns['prod_available_n']


CAP = {}
_orig_prod = AP.prod_available
_prod_n = _make_prod_with_n()


def _capturing_prod(Sin, W, week, L_full, L_upto, st, A_full, A_upto, rookie_qb_sits=False):
    prod, lifted = _orig_prod(Sin, W, week, L_full, L_upto, st, A_full, A_upto, rookie_qb_sits=rookie_qb_sits)
    prod2, lifted2, n = _prod_n(Sin, W, week, L_full, L_upto, st, A_full, A_upto, rookie_qb_sits=rookie_qb_sits)
    assert np.array_equal(np.isnan(prod), np.isnan(prod2)) and np.allclose(prod, prod2, equal_nan=True) and lifted == lifted2
    CAP['n'] = n; CAP['calls'] = CAP.get('calls', 0) + 1
    return prod, lifted


def frame(a):
    """Everything the study needs, built once: rows 2006-2022, n, and each row's 30 matches + weights for In and Base."""
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE, 'rb'))
    C.HORIZON = I.HORIZON
    st, W, Sin, Sb, skipped = I.build(a.nflverse, a.rosters, a.weekly, WEEK)
    L_full, L_upto = I.levels(W)
    players = os.path.join(a.nflverse, 'players.csv')
    AP.prod_available = _capturing_prod
    try:
        SS, none, parts = QS.build_S(Sin, W, st, L_full, L_upto, a, a.sched, a.snaps, players)
    finally:
        AP.prod_available = _orig_prod
    assert CAP['calls'] == 1
    n = CAP['n'].copy()
    n[none] = 0.0                                                      # first-year QB, no game: incoming-rookie value
    rows = Sin.index[(Sin.t >= FIT[0]) & (Sin.t <= TEST[1])].values
    assert Sin.complete.values[rows].all()
    C.W_V['games'] = 0.0
    xr = rows[none[rows]]; vr = rows[~none[rows]]
    nnI, wI = {}, {}
    ti, nn, w = I.match(SS, vr)
    for r, a_, b_ in zip(ti, nn, w): nnI[int(r)] = a_; wI[int(r)] = b_
    if len(xr):
        assert (Sb.kind.values[xr] == 'R0').all()
        ti, nn, w = I.match(Sb, xr)
        for r, a_, b_ in zip(ti, nn, w): nnI[int(r)] = a_; wI[int(r)] = b_
    ti, nn, w = I.match(Sb, rows)
    nnB = {int(r): a_ for r, a_ in zip(ti, nn)}; wB = {int(r): b_ for r, b_ in zip(ti, w)}
    assert set(nnI) == set(int(r) for r in rows) == set(nnB)
    inj = J.injured_weeks(a.weekly, a.wrost, a.inj, WEEK)
    neutral, add = J.neutral_games(Sin, inj, WEEK)
    F = {'Sin': Sin, 'rows': rows, 'n': n, 'none': none, 'add': add,
         'nnI': [nnI[int(r)] for r in rows], 'wI': [wI[int(r)] for r in rows],
         'nnB': [nnB[int(r)] for r in rows], 'wB': [wB[int(r)] for r in rows], 'parts': parts}
    pickle.dump(F, open(CACHE, 'wb'))
    return F


def mix(pin, pbase, n, K):
    w = n / (n + K)
    return w * pin + (1 - w) * pbase


def rmse(p, y):
    return float(np.sqrt(np.mean((p - y) ** 2)))


def pick_K(pin, pbase, n, y, fit):
    sc = {K: rmse(mix(pin[fit], pbase[fit], n[fit], K), y[fit]) for K in GRID}
    return min(sc, key=sc.get), sc


def decide(S, rows, pin, pbase, n, y, fit, test, n_perm=I.N_PERM, with_trades=True):
    K, fit_sc = pick_K(pin, pbase, n, y, fit)
    pm = mix(pin, pbase, n, K)
    lift, p = C.perm_test(y[test], pm[test], pin[test], S.key.values[rows][test], n_perm)
    r = {'K': K, 'fit_rmse_by_K': fit_sc, 'fit_rmse_today': rmse(pin[fit], y[fit]),
         'rmse_mix': rmse(pm[test], y[test]), 'rmse_today': rmse(pin[test], y[test]), 'lift': float(lift), 'p': float(p)}
    if with_trades:
        tr = I.trades(S, rows[test], pm[test], pin[test], y[test])
        r['trades'] = tr
        r['pass'] = bool(lift >= LIFT_BAR and p < ALPHA and tr['diff'] >= TRADE_GUARD / 100)
    else:
        r['pass'] = bool(lift >= LIFT_BAR and p < ALPHA)
    return r, pm


def setup(a):
    F = frame(a)
    S, rows = F['Sin'], F['rows']
    y = np.nan_to_num(S.FV.values.astype(float))
    t = S.t.values[rows]
    fit = (t >= FIT[0]) & (t <= FIT[1]); test = (t >= TEST[0]) & (t <= TEST[1])
    n = F['n'][rows]
    pin, pbase = I.preds(F['nnI'], F['wI'], y), I.preds(F['nnB'], F['wB'], y)
    assert abs(rmse(pin[test], y[rows][test]) - EXPECT_TEST_RMSE_IN) < 1e-6, ('In does not reproduce the adopted value',
                                                                             rmse(pin[test], y[rows][test]))
    return F, S, rows, y, fit, test, n, pin, pbase


def counts(a):
    F, S, rows, y, fit, test, n, pin, pbase = setup(a)
    pool_min = {}
    for r, nn in zip(rows[fit], np.array(F['nnI'], dtype=object)[fit]):
        tt = int(S.t.values[r]); pool_min[tt] = max(pool_min.get(tt, 0), int(S.t.values[nn].max()))
    hist = pd.Series(n).value_counts().sort_index()
    return {'rows_fit': int(fit.sum()), 'rows_test': int(test.sum()), 'test_rmse_today_reproduced': rmse(pin[test], y[rows][test]),
            'n_distribution_all_rows': {int(k): int(v) for k, v in hist.items()},
            'n0_rows': {'fit': int((n[fit] == 0).sum()), 'test': int((n[test] == 0).sum())},
            'first_year_qbs_no_game_test': int(F['none'][rows][test].sum()),
            'latest_pool_season_by_fit_season': pool_min, 'data': F['parts']}


def crash(a, runs, noise_runs=20):
    F, S, rows, y, fit, test, n, pin0, pbase0 = setup(a)
    res = {}
    rng = np.random.default_rng(7)
    grp = pd.DataFrame({'p': S.pos.values, 't': S.t.values}).groupby(['p', 't']).groups
    npass = 0; ks = []
    for i in range(noise_runs):
        yn = y.copy()
        for g in grp.values():
            g = np.array(list(g)); yn[g] = y[rng.permutation(g)]
        pin, pbase = I.preds(F['nnI'], F['wI'], yn), I.preds(F['nnB'], F['wB'], yn)
        r, _ = decide(S, rows, pin, pbase, n, yn[rows], fit, test, n_perm=1000, with_trades=False)
        npass += r['pass']; ks.append(r['K'])
    res['noise'] = {'runs': noise_runs, 'passed': int(npass), 'ok': npass <= 1, 'K_picked': ks}
    print('noise', res['noise'], flush=True)
    truth0 = mix(pin0, pbase0, n, PLANT_K)
    resid = y[rows] - truth0; pos = S.pos.values[rows]
    rng = np.random.default_rng(75); ok = 0; lifts = []; ks = []
    for i in range(runs):
        e = resid.copy()
        for ps in C.POS:
            m = np.where(pos == ps)[0]; e[m] = resid[rng.permutation(m)]
        truth = np.maximum(0.0, truth0 + e)
        r, _ = decide(S, rows, pin0, pbase0, n, truth, fit, test, n_perm=1000, with_trades=False)
        ok += r['pass']; lifts.append(r['lift']); ks.append(r['K'])
    res['planted_K4'] = {'runs': runs, 'passed': int(ok), 'share': ok / runs, 'ok': ok / runs >= 0.80,
                         'median_lift': float(np.median(lifts)), 'K_picked': {int(k): ks.count(k) for k in sorted(set(ks))}}
    print('planted', res['planted_K4'], flush=True)
    return res


def run(a):
    F, S, rows, y, fit, test, n, pin, pbase = setup(a)
    yr = y[rows]
    r, pm = decide(S, rows, pin, pbase, n, yr, fit, test)
    res = {'prereg': 'docs/PREREG-ovs-small-samples.md', 'week': WEEK, 'decides': r}
    res['every_K_on_test'] = {K: {'rmse': rmse(mix(pin, pbase, n, K)[test], yr[test]),
                                  'lift_vs_today': float(1 - rmse(mix(pin, pbase, n, K)[test], yr[test]) / rmse(pin[test], yr[test]))} for K in GRID}
    pos = S.pos.values[rows]
    res['by_position'] = {q: {'rows': int((test & (pos == q)).sum()),
                              'lift': float(1 - rmse(pm[test & (pos == q)], yr[test & (pos == q)]) / rmse(pin[test & (pos == q)], yr[test & (pos == q)]))} for q in C.POS}
    add = F['add'][rows]; rook = S.rookie_Y.values[rows].astype(bool)
    vet = S.kind.values[rows] == 'V'
    groups = {'rookies': rook, 'low_games_never_hurt': (S.games.values[rows] <= 5) & (add == 0) & vet, 'out_hurt_2plus': add >= 2,
              'healthy_vets_6plus_games': (n >= 6) & (add == 0) & ~rook, 'veterans_no_game_this_season': (n == 0) & ~rook}
    res['groups_produced_over_value'] = {g: {'rows': int((m & test).sum()),
                                             'today': float(yr[m & test].sum() / pin[m & test].sum()),
                                             'mix': float(yr[m & test].sum() / pm[m & test].sum()),
                                             'rmse_today': rmse(pin[m & test], yr[m & test]), 'rmse_mix': rmse(pm[m & test], yr[m & test])}
                                         for g, m in groups.items()}
    res['decision'] = f'mix with K = {r["K"]}' if r['pass'] else 'no change'
    return res


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'weekly', 'wrost', 'inj', 'sched', 'snaps'): ap.add_argument('--' + k, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--counts', action='store_true'); g.add_argument('--crash', action='store_true'); g.add_argument('--run', action='store_true')
    ap.add_argument('--runs', type=int, default=200)
    a = ap.parse_args()
    if a.counts:
        res = counts(a); name = 'ovs_small_samples_counts.json'
    elif a.crash:
        res = crash(a, a.runs); name = 'ovs_small_samples_crash.json'
        print('crash tests:', 'PASS' if res['noise']['ok'] and res['planted_K4']['ok'] else 'FAIL')
    else:
        res = run(a); name = 'ovs_small_samples_results.json'
    json.dump(res, open(os.path.join(OUT, name), 'w'), indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
