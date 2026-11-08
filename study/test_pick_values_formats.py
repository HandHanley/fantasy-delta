#!/usr/bin/env python3
"""
CRASH TESTS for pick_values_formats.py — docs/PREREG-pick-values-formats.md §4.

Same worlds as test_pick_values.py (tilt planted in the veterans; noise swapped within position and OVS tenth), on
the two formats furthest from DELTA's: 10-team 1QB Standard and 14-team Superflex Full PPR with TE premium.
Also checks the format switch really changes the points and the lines. No pick outcome is compared with a veteran's.

    python test_pick_values_formats.py --nflverse DIR --rosters DIR [--runs 100]
"""
import argparse, json, os, time
import numpy as np
import comps_value_study as C
import pick_values as P
import pick_values_formats as F

FORMATS = [(10, '1QB', 0.0, 0.0), (14, 'SF', 1.0, 0.5)]


def worlds(picks, vet, M, runs, boot, tag):
    ok = vet['ovs'] > 0
    ratio_v = np.where(ok, vet['y'] / np.where(ok, vet['ovs'], 1), np.nan)
    L = np.array([picks['y'][picks['tier'] == k].mean() for k in range(len(P.TIERS))])
    Lp = L[picks['tier']]; eps0 = picks['y'] / Lp
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

    res = {}
    for R_true, key in ((1.0, 'fair'), (0.7, 'tilted_0.7')):
        rng = np.random.default_rng(int(R_true * 100) + tag)
        inc, Rs = 0, []
        for i in range(runs):
            yp, yv = world(R_true, rng)
            Rs.append(P.estimate(picks, vet, M, yp, yv)[0])
            inc += P.bootstrap(picks, vet, M, yp, yv, n_boot=boot, seed=1000 + i, with_groups=False)['includes_1']
        res[key] = {'runs': runs, 'range_includes_1': inc, 'median_R': float(np.median(Rs))}
    res['fair']['ok'] = res['fair']['range_includes_1'] / runs >= 0.90
    res['tilted_0.7']['ok'] = (runs - res['tilted_0.7']['range_includes_1']) / runs >= 0.80
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    ap.add_argument('--runs', type=int, default=100); ap.add_argument('--boot', type=int, default=1000)
    a = ap.parse_args()
    out, t0 = {}, time.time()
    for j, f in enumerate(FORMATS):
        F.apply(f)
        st, dp, pl = C.load(a.nflverse, a.rosters)
        exp = st.fantasy_points.fillna(0) + f[2] * st.receptions + np.where(st.position == 'TE', f[3] * st.receptions, 0)
        assert np.allclose(st.P, exp) and not np.allclose(st.P, (st.fantasy_points.fillna(0) + st.fantasy_points_ppr.fillna(0)) / 2
                                                           + np.where(st.position == 'TE', 0.5 * st.receptions, 0))
        assert C.REPL_N == F.lines(f[0], f[1]) and C.REPL_N != F._ORIG_REPL
        st, S, picks, vet, counts = P.setup(a.nflverse, a.rosters)
        r = worlds(picks, vet, P.Matcher(vet), a.runs, a.boot, tag=j)
        r['lines'] = C.REPL_N
        out[F.name(f)] = r
        print(F.name(f), r, f'{time.time() - t0:.0f}s', flush=True)
    ok = all(v['fair']['ok'] and v['tilted_0.7']['ok'] for v in out.values())
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'pick_values_formats_crash.json')
    json.dump(out, open(dst, 'w'), indent=1, default=float)
    print('crash tests:', 'PASS' if ok else 'FAIL')


if __name__ == '__main__':
    main()
