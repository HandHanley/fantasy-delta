#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE, ERA-ADJUSTED MATCHING. Implements docs/PREREG-ovs-era.md; where they disagree, the
pre-registration (with its amendments) wins.

One change to the locked Own Value Scale (own_value_scale.py): a veteran's recent production is matched as a share of
that season's typical starter at his position, not as raw points per game. Each season's points per game is divided by
that season's starter level (the average points per game of the top 24 QBs, RBs, WRs or top 12 TEs with 8+ games)
before the 3/2/1 weighting. Rookies (draft slot + age), age, games, career year, weights, 30 matches, pool, outcome: all
unchanged.

    python ovs_era.py --nflverse DIR --rosters DIR --counts-only
    python ovs_era.py --nflverse DIR --rosters DIR --crash [--runs 200]   # before lock
    python ovs_era.py --nflverse DIR --rosters DIR --run                  # once, after lock
"""
import argparse, json, os, time
import numpy as np
import pandas as pd
import comps_value_study as C
import comps_draft_drop as DD
import own_value_scale as V

LIFT_BAR = 0.02
ALPHA = 0.05            # one deciding question (Q1); project rule
TRADE_GUARD = -1.0      # Q2 point estimate may not be worse than this (points)
N_PERM = 10_000
MIN_GAMES = 8
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')


def starter_level(st):
    """(season, position) -> average points per game of the top STARTER_N with MIN_GAMES+ games."""
    q = st[st.games >= MIN_GAMES].copy(); q['ppg'] = q.P / q.games
    return {(int(yr), ps): float(g.ppg.nlargest(C.STARTER_N[ps]).mean()) for (yr, ps), g in q.groupby(['season', 'position'])}


def era_prod(st, S):
    """Era-adjusted 3/2/1 production for every veteran row, in units of 'share of that season's starter level'."""
    lvl = starter_level(st)
    pts = {(r.player_id, int(r.season)): (float(r.P), float(r.games), r.position) for r in st.itertuples()}
    out = np.full(len(S), np.nan)
    for i, (k, t, kind) in enumerate(zip(S.key.values, S.t.values, S.kind.values)):
        if kind != 'V': continue
        num = den = 0.0
        for w, yr in ((3, t), (2, t - 1), (1, t - 2)):
            P_, g, ps = pts.get((k, int(yr)), (0.0, 0.0, None))
            if g >= 1:
                num += w * (P_ / g) / lvl[(int(yr), ps)]; den += w
        out[i] = num / den
    # same seasons played as the locked feature (a row's raw and era production use the same games)
    v = S.kind.values == 'V'
    assert not np.isnan(out[v]).any(), 'a veteran row has no era production'
    return out, lvl


def setup(nflverse, rosters):
    st, S, pre, nnA, W, counts = V.setup(nflverse, rosters)          # the locked OVS, unchanged
    S2 = S.copy()
    S2['prod'], lvl = era_prod(st, S)
    S2.loc[S2.kind == 'R0', 'prod'] = np.nan
    T = pre['test']
    pa = DD.neighbours(S2, T, 'A')
    assert np.array_equal(pa['test'], T), 'era rows differ from the locked rows'
    for r, nn in zip(T, pa['nn'][30]):
        assert (S2.t.values[nn] <= S2.t.values[r] - 5).all(), 'pool leak'
        assert S2.key.values[r] not in set(S2.key.values[nn]), 'self in pool'
    W2 = []
    for r, nn in zip(T, pa['nn'][30]):
        w = 0.5 ** ((S2.t.values[r] - S2.t.values[nn]) / V.HALF_LIFE); W2.append(w / w.sum())
    # rookies are untouched: their matches must be identical
    rk = S.kind.values[T] == 'R0'
    same = [np.array_equal(a, b) for a, b, k in zip(nnA, pa['nn'][30], rk) if k]
    assert all(same), 'rookie matches changed'
    counts['rookie_rows_unchanged'] = int(len(same))
    counts['starter_level_examples'] = {f'{p} {y}': round(lvl[(y, p)], 2) for p in C.POS for y in (2004, 2008, 2016, 2025)}
    return st, S, S2, pre, nnA, W, pa['nn'][30], W2, counts


def preds(nn, W, y):
    return np.array([(w * y[n]).sum() for n, w in zip(nn, W)])


def q1(S, pre, p_new, p_old, yt, n_perm=N_PERM):
    cl = S.key.values[pre['test']]
    lift, p = C.perm_test(yt, p_new, p_old, cl, n_perm)
    return {'rmse_era': C.rmse(p_new, yt), 'rmse_locked': C.rmse(p_old, yt), 'lift': float(lift), 'p': float(p),
            'pass': bool(lift >= LIFT_BAR and p < ALPHA)}


def q2(S, pre, p_new, p_old, yt, n_perm=N_PERM, seed=13):
    A, B, K = V.build_trades(S, pre, p_new, p_old)
    r = V.q2(S, pre, p_new, p_old, yt, A, B, K, n_perm=n_perm, seed=seed)
    return {'n_trades': r['n_trades'], 'acc_era': r['acc_ovs'], 'acc_locked': r['acc_b2'], 'diff': r['diff'], 'p': r['p'],
            'guard_ok': bool(r['diff'] >= TRADE_GUARD / 100)}


def calibration(S, pre, p, y):
    T = pre['test']; v = S.kind.values[T] == 'V'
    out = {}
    for ps in C.POS:
        m = v & (S.pos.values[T] == ps) & (p > 60)
        out[ps] = {'n': int(m.sum()), 'produced_over_predicted': round(float(y[T][m].sum() / p[m].sum()), 3)}
    return out


def crash(S, S2, pre, nnA, W, nn2, W2, y, runs, noise_runs=20):
    rng = np.random.default_rng(7); T = pre['test']; res = {}
    noise = []
    for i in range(noise_runs):                       # outcomes shuffled within position and season
        yn = y.copy()
        for (ps, t), g in pd.DataFrame({'p': S.pos.values, 't': S.t.values}).groupby(['p', 't']).groups.items():
            g = np.array(list(g)); yn[g] = y[rng.permutation(g)]
        r = q1(S, pre, preds(nn2, W2, yn), preds(nnA, W, yn), yn[T], n_perm=1000)
        noise.append(r['pass'])
    res['noise'] = {'runs': noise_runs, 'passed': int(sum(noise)), 'ok': sum(noise) <= 1}
    print('noise', res['noise'], flush=True)
    pe, pl = preds(nn2, W2, y), preds(nnA, W, y)
    resid = y[T] - pl; pos = S.pos.values[T]
    for w, n, key in ((0.75, runs, 'planted_0.75'), (0.6, max(20, runs // 4), 'planted_0.6')):
        rng = np.random.default_rng(int(w * 100)); ok = 0; lifts = []
        for i in range(n):
            e = resid.copy()
            for ps in C.POS:
                m = np.where(pos == ps)[0]; e[m] = resid[rng.permutation(m)]
            truth = np.maximum(0.0, pl + w * (pe - pl) + e)
            r = q1(S, pre, pe, pl, truth, n_perm=1000); ok += r['pass']; lifts.append(r['lift'])
        res[key] = {'runs': n, 'passed': int(ok), 'share': ok / n, 'median_lift': float(np.median(lifts))}
        if w == 0.75: res[key]['ok'] = ok / n >= 0.80
        print(key, res[key], flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--counts-only', action='store_true'); g.add_argument('--crash', action='store_true')
    g.add_argument('--run', action='store_true')
    ap.add_argument('--runs', type=int, default=200)
    a = ap.parse_args()
    st, S, S2, pre, nnA, W, nn2, W2, counts = setup(a.nflverse, a.rosters)
    y = S.FV.values.astype(float); T = pre['test']
    print(json.dumps(counts, indent=1, default=float))
    if a.counts_only: return
    if a.crash:
        res = crash(S, S2, pre, nnA, W, nn2, W2, y, a.runs)
        res['counts'] = counts
        json.dump(res, open(os.path.join(OUT, 'ovs_era_crash.json'), 'w'), indent=1, default=float)
        print('crash tests:', 'PASS' if res['noise']['ok'] and res['planted_0.75']['ok'] else 'FAIL')
        return
    pe, pl = preds(nn2, W2, y), preds(nnA, W, y)
    locked = V.predictions(S, pre, nnA, W, y)['OVS']
    assert np.allclose(pl, locked), 'locked OVS not reproduced'
    yt = y[T]
    res = {'prereg': 'docs/PREREG-ovs-era.md', 'counts': counts, 'Q1': q1(S, pre, pe, pl, yt), 'Q2': q2(S, pre, pe, pl, yt),
           'calibration_era': calibration(S, pre, pe, y), 'calibration_locked': calibration(S, pre, pl, y)}
    res['decision'] = 'adopt era matching' if res['Q1']['pass'] and res['Q2']['guard_ok'] else 'keep locked matching'
    json.dump(res, open(os.path.join(OUT, 'ovs_era_results.json'), 'w'), indent=1, default=float)
    print(json.dumps({k: res[k] for k in ('Q1', 'Q2', 'calibration_era', 'calibration_locked', 'decision')}, indent=1, default=float))


if __name__ == '__main__':
    main()
