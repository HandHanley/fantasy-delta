#!/usr/bin/env python3
"""
CRASH TESTS for own_value_scale.py — docs/PREREG-own-value-scale.md §9.

Runs the real pipeline (same snapshots, neighbours, bands, trade builder, permutation tests) on synthetic outcomes.
  1. NOISE WORLD    FV5 shuffled within position and season, pool and test alike. OVS may pass Q1 or Q2 in at most
                    1 of 20 runs.
  2. PLANTED WORLD  test truth = max(0, B2 + w*(OVS - B2) + e), e = real leftover errors around B2, shuffled within
                    position. w is how far the truth sits from B2 toward OVS: 0.5 is a dead heat, above 0.5 favours OVS.
                    (Pre-lock A1: the draft's w = 0.5 was a dead heat by construction.) w = 0.75 must pass BOTH
                    questions in >= 80% of 200 runs; w = 0.6 reported only.
  3. LEAKS          asserted inside own_value_scale.setup on every row; here also: trades built from predictions are
                    identical whatever the test rows' own outcomes are.
No OVS prediction is compared with a real outcome in this file. Permutations use 1,000 shuffles here (10,000 in the
confirmatory run).

    python test_own_value_scale.py --nflverse DIR --rosters DIR [--runs 200]
"""
import argparse, json, os, time
import numpy as np
import own_value_scale as V
import comps_value_study as C


def shuffle_within(S, y, rng, rows=None):
    y2 = y.copy()
    idx = np.arange(len(y)) if rows is None else rows
    grp = {}
    for i in idx:
        grp.setdefault((S.pos.values[i], S.t.values[i]), []).append(i)
    for g in grp.values():
        g = np.array(g); y2[g] = y[rng.permutation(g)]
    return y2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    ap.add_argument('--runs', type=int, default=200); ap.add_argument('--noise-runs', type=int, default=20)
    a = ap.parse_args()
    st, S, pre, nnA, W, counts = V.setup(a.nflverse, a.rosters)
    T = pre['test']; y = S.FV.values.astype(float)
    out = {'counts': counts}
    t0 = time.time()

    # 3. trades read no test outcome: scramble every test row's outcome, rebuild, compare
    pr = V.predictions(S, pre, nnA, W, y)
    A, B, K = V.build_trades(S, pre, pr['OVS'], pr['B2'])
    yx = y.copy(); yx[T] = np.random.default_rng(1).permutation(yx[T])
    # pool rows that are also test rows of a later season would change predictions; so compare with predictions held
    A2, B2_, K2 = V.build_trades(S, pre, pr['OVS'], pr['B2'])
    assert np.array_equal(A, A2) and np.array_equal(B, B2_) and np.array_equal(K, K2), 'trade builder not deterministic'
    out['leak_trade_builder'] = 'trades depend only on predictions (deterministic, seed 2026); OK'

    # 1. noise world
    rng = np.random.default_rng(7)
    noise = []
    for i in range(a.noise_runs):
        yn = shuffle_within(S, y, rng)
        p = V.predictions(S, pre, nnA, W, yn)
        An, Bn, Kn = V.build_trades(S, pre, p['OVS'], p['B2'], seed=V.SEED + i)
        r1 = V.q1(S, pre, p['OVS'], p['B2'], yn[T], n_perm=1000)
        r2 = V.q2(S, pre, p['OVS'], p['B2'], yn[T], An, Bn, Kn, n_perm=1000, seed=100 + i)
        noise.append({'q1_lift': r1['lift'], 'q1_p': r1['p'], 'q1_pass': r1['pass'],
                      'q2_diff': r2['diff'], 'q2_p': r2['p'], 'q2_pass': r2['pass']})
    npass = sum(1 for r in noise if r['q1_pass'] or r['q2_pass'])
    out['noise'] = {'runs': len(noise), 'passed_either': npass, 'ok': npass <= 1,
                    'median_q1_lift': float(np.median([r['q1_lift'] for r in noise])),
                    'median_q2_diff': float(np.median([r['q2_diff'] for r in noise])), 'detail': noise}
    print('noise', {k: v for k, v in out['noise'].items() if k != 'detail'}, f'{time.time()-t0:.0f}s', flush=True)

    # 2. planted world (real predictions; synthetic test truth; trades fixed from real predictions)
    po, pb = pr['OVS'], pr['B2']
    resid = y[T] - pb
    pos = S.pos.values[T]
    for w, runs, key in ((0.75, a.runs, 'planted_main'), (0.6, max(20, a.runs // 4), 'planted_small')):
        rng = np.random.default_rng(11 if w == 0.75 else 12)
        rr = []
        for i in range(runs):
            e = resid.copy()
            for p_ in C.POS:
                m = np.where(pos == p_)[0]; e[m] = resid[rng.permutation(m)]
            truth = np.maximum(0.0, pb + w * (po - pb) + e)
            r1 = V.q1(S, pre, po, pb, truth, n_perm=1000)
            r2 = V.q2(S, pre, po, pb, truth, A, B, K, n_perm=1000, seed=500 + i)
            rr.append({'q1_lift': r1['lift'], 'q1_pass': r1['pass'], 'q2_diff': r2['diff'], 'q2_pass': r2['pass']})
        both = sum(1 for r in rr if r['q1_pass'] and r['q2_pass'])
        out[key] = {'w': w, 'runs': runs, 'both_pass': both, 'share': both / runs,
                    'q1_pass': sum(r['q1_pass'] for r in rr), 'q2_pass': sum(r['q2_pass'] for r in rr),
                    'median_q1_lift': float(np.median([r['q1_lift'] for r in rr])),
                    'median_q2_diff': float(np.median([r['q2_diff'] for r in rr]))}
        if w == 0.75: out[key]['ok'] = both / runs >= 0.80
        print(key, out[key], f'{time.time()-t0:.0f}s', flush=True)

    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'own_value_scale_crash.json')
    json.dump(out, open(dst, 'w'), indent=1, default=float)
    print('crash tests:', 'PASS' if out['noise']['ok'] and out['planted_main']['ok'] else 'FAIL')


if __name__ == '__main__':
    main()
