#!/usr/bin/env python3
"""
CRASH TESTS for pick_values.py — docs/PREREG-pick-values.md §7.

Runs the real estimator and resampling on synthetic outcomes. A pick's value is its tier's own average, so a tilt
between picks and veterans can only show up as veterans producing more or less than their value says. The worlds
are built that way (pre-lock amendment A1):
  veterans   y = OVS x eta / R_true   eta = real veteran outcome-to-OVS ratios, shuffled within position, mean 1
  picks      y = L_tier x eps         L = tier averages, eps = pick outcome-to-tier ratios, shuffled, mean 1
  1. FAIR    R_true = 1.0: the 95% range must include 1.0 in >= 90% of 200 runs.
  2. TILTED  R_true = 0.7: the range must exclude 1.0 in >= 80% of 200 runs. R_true = 1.3 reported (50 runs).
  3. LEAKS   matching reads predictions only (scrambling veteran outcomes leaves every match unchanged);
             a class never helps value itself (changing one class's outcomes leaves its own pick values unchanged).
No pick outcome is compared with a veteran outcome in this file. 1,000 resamples per run here (4,000 confirmatory).

    python test_pick_values.py --nflverse DIR --rosters DIR [--runs 200]
"""
import argparse, json, os, time
import numpy as np
import pick_values as P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    ap.add_argument('--runs', type=int, default=200); ap.add_argument('--boot', type=int, default=1000)
    a = ap.parse_args()
    st, S, picks, vet, counts = P.setup(a.nflverse, a.rosters)
    M = P.Matcher(vet)
    out = {'counts': counts, 'boot_per_run': a.boot}
    t0 = time.time()

    # 3. leaks
    rng = np.random.default_rng(3)
    e1 = P.estimate(picks, vet, M, picks['y'], vet['y'], detail=True)
    e2 = P.estimate(picks, vet, M, picks['y'], rng.permutation(vet['y']), detail=True)
    assert np.array_equal(e1['width'], e2['width'], equal_nan=True) and np.array_equal(e1['n_vets'], e2['n_vets'])
    for c in P.CLASSES:
        y2 = picks['y'].copy(); mk = picks['cls'] == c
        y2[mk] = rng.permutation(y2[mk]) * 3 + 50
        assert np.allclose(P.tier_values(picks, y2, np.ones(len(y2)))[c], e1['tv'][c]), c
    out['leaks'] = 'matching reads OVS only; each class valued only from the other seven; OK'

    # synthetic ingredients
    ok = vet['ovs'] > 0
    ratio_v = np.where(ok, vet['y'] / np.where(ok, vet['ovs'], 1), np.nan)
    L = np.array([picks['y'][picks['tier'] == k].mean() for k in range(len(P.TIERS))])
    Lp = L[picks['tier']]
    eps0 = picks['y'] / Lp

    # veterans grouped by position and OVS tenth: a ratio is only swapped among veterans of a similar value,
    # and each group's ratios are scaled to average exactly 1, so the fair world's veterans are calibrated
    grp = []
    for p in ('QB', 'RB', 'WR', 'TE'):
        m = np.where((vet['pos'] == p) & ok)[0]
        cuts = np.quantile(vet['ovs'][m], np.linspace(0, 1, 11)[1:-1])
        b = np.searchsorted(cuts, vet['ovs'][m], 'right')
        grp += [m[b == j] for j in range(10) if (b == j).any()]

    def world(R_true, rng):
        eta = np.ones(len(vet['y']))
        for g in grp:
            r = ratio_v[rng.permutation(g)]
            eta[g] = r / r.mean() if r.mean() > 0 else 1.0
        yv = np.where(ok, vet['ovs'] * eta / R_true, 0.0)
        eps = rng.permutation(eps0); eps /= eps.mean()
        return Lp * eps, yv

    for R_true, runs, key in ((1.0, a.runs, 'fair'), (0.7, a.runs, 'tilted_0.7'), (1.3, max(20, a.runs // 4), 'tilted_1.3')):
        rng = np.random.default_rng(int(R_true * 100))
        rr = []
        for i in range(runs):
            yp, yv = world(R_true, rng)
            R = P.estimate(picks, vet, M, yp, yv)[0]
            ci = P.bootstrap(picks, vet, M, yp, yv, n_boot=a.boot, seed=1000 + i, with_groups=False)
            rr.append({'R': float(R), 'lo': ci['lo'], 'hi': ci['hi'], 'includes_1': ci['includes_1']})
        inc = sum(r['includes_1'] for r in rr)
        out[key] = {'R_true': R_true, 'runs': runs, 'range_includes_1': inc, 'share_includes_1': inc / runs,
                    'median_R': float(np.median([r['R'] for r in rr])),
                    'median_width': float(np.median([r['hi'] - r['lo'] for r in rr]))}
        if key == 'fair': out[key]['ok'] = inc / runs >= 0.90
        if key == 'tilted_0.7': out[key]['ok'] = (runs - inc) / runs >= 0.80
        print(key, out[key], f'{time.time() - t0:.0f}s', flush=True)

    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'pick_values_crash.json')
    json.dump(out, open(dst, 'w'), indent=1, default=float)
    print('crash tests:', 'PASS' if out['fair']['ok'] and out['tilted_0.7']['ok'] else 'FAIL')


if __name__ == '__main__':
    main()
