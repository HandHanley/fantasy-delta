#!/usr/bin/env python3
"""
CRASH TESTS for comps_value_study.py — docs/PREREG-comparables-value.md §8.

Runs the REAL pipeline (same snapshots, same neighbours, same bands, same permutation test)
on synthetic outcomes, so every result here is about the method, not about football.

  1. NOISE WORLD      FV shuffled among snapshots of the same position and season.
                      CV must NOT pass Q1 or Q2.
  2. PLANTED WORLD    FV = B2's own prediction, times a draft-capital extra for young players
                      that B2 cannot see, times noise averaging exactly 1. CV should pass Q2 in
                      at least 80% of 200 runs, or the study is underpowered for Q2.
  3. THRESHOLD WORLD  Only top-10 picks ever produce. CV must not report a smooth slope
                      through picks 11+ that isn't there.
  4. LEAK CHECKS      Pool seasons <= t-5, nobody in his own pool (asserted inside
                      precompute on every row), and eligibility/features read nothing after t
                      (asserted here by rebuilding with later seasons deleted).

No real outcome is compared with any CV prediction anywhere in this file. Real FV enters only
shuffled (world 1), through B2's band averages (world 2's base) and as a level (world 3).

Usage:  python test_comps_value.py --data DIR [--runs 200] [--out study/out/comps_value_crash.json]
"""
import argparse, json, os, sys, time
import numpy as np
import pandas as pd
import comps_value_study as C

PLANT_RATIO = 0.70 / 0.38       # 1 Nov illustration: Harrison-like 70% vs Lemon-like 38%
THRESH_FLAG = 0.30              # world 3: CV mean at picks 11-15 above 30% of picks 6-10 = smooth leak


def leak_checks(st, dp, pl, S):
    """Eligibility and features at season T are identical when every season after T is deleted."""
    feats = ['kind', 'key', 't', 'pos', 'prod', 'games', 'age', 'cy', 'pick', 'draft', 'undrafted', 'G']
    out = []
    for T in (2008, 2013, 2016, 2020):
        Sx, _ = C.build(st[st.season <= T], dp, pl, snap_last=T, check_complete=False)
        a = S[S.t == T][feats].sort_values(['kind', 'key']).reset_index(drop=True)
        b = Sx[Sx.t == T][feats].sort_values(['kind', 'key']).reset_index(drop=True)
        assert len(a) == len(b), f'eligibility at {T} changes when later seasons are deleted ({len(a)} vs {len(b)})'
        pd.testing.assert_frame_equal(a, b, check_dtype=False)
        out.append({'season': T, 'snapshots': len(a), 'identical': True})
    return out


def noise_world(S, pre, runs, seed=100):
    rng = np.random.default_rng(seed)
    y0 = S.FV.values.astype(float)
    grp = S.groupby(['pos', 't']).indices
    res = []
    for i in range(runs):
        y = y0.copy()
        for idx in grp.values():
            y[idx] = y0[rng.permutation(idx)]
        q, _ = C.questions(S, pre, y, seed=1000 + i)
        res.append({'Q1_lift': q['Q1']['lift'], 'Q1_p': q['Q1']['p'], 'Q1_pass': q['Q1']['pass'],
                    'Q2_lift': q['Q2']['lift'], 'Q2_p': q['Q2']['p'], 'Q2_pass': q['Q2']['pass'],
                    'Q2_base': q['Q2']['baseline']})
    return res


def b2_full(S):
    """B2's band membership for every snapshot, from all other players' snapshots (no time rule:
    this builds a synthetic world's base, it is not a forecast)."""
    mem = []
    keys = S.key.values
    for r in range(len(S)):
        pv = S.index[(S.pos == S.at[r, 'pos']) & (S.kind == S.at[r, 'kind']) & (S.key != keys[r])].values
        mem.append(C._b2(S, r, pv, S.at[r, 'kind']))
    return mem


def plant_multiplier(S):
    young = (S.cy.values <= 2) & ~S.undrafted.values.astype(bool)
    pick = S.pick.values.astype(float)
    top = young & (pick <= 10); mid = young & (pick >= 11) & (pick <= 32)
    lo, hi = 0.0, 3.0
    for _ in range(60):                     # solve beta so mean m(top)/mean m(mid) = PLANT_RATIO
        b = (lo + hi) / 2
        m = pick ** -b
        if m[top].mean() / m[mid].mean() < PLANT_RATIO: lo = b
        else: hi = b
    m = np.ones(len(S))
    yb = (S.cy.values <= 2)
    raw = np.where(S.undrafted.values.astype(bool), C.UNDRAFTED_PICK, pick) ** -b
    m[yb] = raw[yb] / raw[yb].mean()
    return b, m


def planted_world(S, pre, runs, base, mult, sd, seed=200):
    rng = np.random.default_rng(seed)
    res = []
    for i in range(runs):
        noise = rng.lognormal(-sd ** 2 / 2, sd, len(S))
        y = base * mult * noise
        q, _ = C.questions(S, pre, y, seed=2000 + i)
        res.append({'Q1_lift': q['Q1']['lift'], 'Q1_pass': q['Q1']['pass'],
                    'Q2_lift': q['Q2']['lift'], 'Q2_p': q['Q2']['p'], 'Q2_pass': q['Q2']['pass'],
                    'Q2_base': q['Q2']['baseline']})
    return res


def threshold_world(S, pre, seed=300):
    rng = np.random.default_rng(seed)
    pick = S.pick.values; und = S.undrafted.values.astype(bool)
    hit = (~und) & (pick <= 10)
    y = np.zeros(len(S))
    real = S.FV.values.astype(float)
    for p in C.POS:
        m = hit & (S.pos.values == p)
        lvl = real[m].mean()                  # a level only; no prediction is compared with it
        y[m] = lvl * rng.lognormal(-0.5, 1.0, m.sum())
    pr = C.predict(pre, y)
    T = pre['test']; young = S.cy.values[T] <= 2
    pk = pick[T]; ud = und[T]
    bands = {'1-5': (1, 5), '6-10': (6, 10), '11-15': (11, 15), '16-20': (16, 20), '21-32': (21, 32), '33-64': (33, 64),
             '65+': (65, 10 ** 6)}
    tab = {}
    for lab, (lo, hi) in bands.items():
        m = young & ~ud & (pk >= lo) & (pk <= hi)
        tab[lab] = {'n': int(m.sum()), 'truth': float(y[T][m].mean()),
                    'CV': float(pr['CV'][m].mean()), 'B3': float(pr['B3'][m].mean())}
    leak = tab['11-15']['CV'] / tab['6-10']['CV'] if tab['6-10']['CV'] else float('nan')
    return {'table': tab, 'cv_11_15_over_6_10': leak, 'flag': bool(leak > THRESH_FLAG)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True)
    ap.add_argument('--runs', type=int, default=200)
    ap.add_argument('--noise-runs', type=int, default=20)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out',
                                                 'comps_value_crash.json'))
    a = ap.parse_args()
    t0 = time.time()
    st, dp, pl = C.load(a.data)
    S_all, counts = C.build(st, dp, pl)
    S = S_all[S_all.t <= C.SNAP_LAST].reset_index(drop=True)
    out = {'counts': counts}
    out['leak'] = leak_checks(st, dp, pl, S); print('leak checks passed', out['leak'], flush=True)
    pre = C.precompute(S)
    print('precompute', round(time.time() - t0), 's', flush=True)

    nz = noise_world(S, pre, a.noise_runs)
    out['noise'] = {'runs': len(nz), 'Q1_passes': sum(r['Q1_pass'] for r in nz),
                    'Q2_passes': sum(r['Q2_pass'] for r in nz),
                    'Q1_lift_mean': float(np.mean([r['Q1_lift'] for r in nz])),
                    'Q2_lift_mean': float(np.mean([r['Q2_lift'] for r in nz])), 'detail': nz}
    print('noise', {k: v for k, v in out['noise'].items() if k != 'detail'}, flush=True)

    mem = b2_full(S)
    real = S.FV.values.astype(float)
    base = np.array([real[m].mean() for m in mem])
    beta, mult = plant_multiplier(S)
    # noise sd: the synthetic world scatters around its own truth as far as real outcomes scatter
    # around B2's band averages (B2's in-sample fit, no time rule; no CV prediction is involved).
    # Matching the raw outcome spread instead gave sd ~0.46, a world far cleaner than reality,
    # which would overstate power (lesson 15).
    target = float(np.sqrt(np.mean((real - base) ** 2)))
    lo, hi = 0.05, 5.0
    for _ in range(40):
        sd = (lo + hi) / 2
        z = np.random.default_rng(0).lognormal(-sd ** 2 / 2, sd, len(S))
        if np.sqrt(np.mean((base * mult * z - base * mult) ** 2)) < target: lo = sd
        else: hi = sd
    pw = planted_world(S, pre, a.runs, base, mult, sd)
    out['planted'] = {'runs': len(pw), 'beta': beta, 'noise_sd': sd, 'ratio_target': PLANT_RATIO,
                      'Q2_pass_rate': sum(r['Q2_pass'] for r in pw) / len(pw),
                      'Q1_pass_rate': sum(r['Q1_pass'] for r in pw) / len(pw),
                      'Q2_lift_median': float(np.median([r['Q2_lift'] for r in pw])),
                      'Q2_baselines': pd.Series([r['Q2_base'] for r in pw]).value_counts().to_dict(),
                      'powered': None}
    out['planted']['powered'] = out['planted']['Q2_pass_rate'] >= 0.80
    print('planted', out['planted'], flush=True)

    out['threshold'] = threshold_world(S, pre)
    print('threshold', json.dumps(out['threshold'], indent=1), flush=True)

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w') as f:
        json.dump(out, f, indent=1, default=float)
    ok = out['noise']['Q1_passes'] == 0 and out['noise']['Q2_passes'] == 0
    print('\nCRASH TESTS:', 'noise OK' if ok else 'NOISE PASSED — investigate before lock',
          '| planted power', out['planted']['Q2_pass_rate'],
          '| threshold flag', out['threshold']['flag'], '|', round(time.time() - t0), 's')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
