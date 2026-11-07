#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE (NO MARKET). Implements docs/PREREG-own-value-scale.md; where they disagree, the
pre-registration (with its section 12 amendments) wins.

OVS = Version A comparables (comps_draft_drop, mode 'A'), Fix 2 weights (0.5 ** ((t - s) / 8)), averaged FV5.
Q1: RMSE on FV5 vs B2 (production + age), 2013-2020, lift >= 2%, p < 0.025.
Q2: share of synthetic trades called right vs B2, +2.0 points, p < 0.025.
No market data of any kind is read. Data: nflverse (credit nflverse).

    python own_value_scale.py --nflverse DIR --rosters DIR --counts-only
    python own_value_scale.py --nflverse DIR --rosters DIR                 # confirmatory (once, after lock)
"""
import argparse, json, math, os
import numpy as np
import pandas as pd
import comps_value_study as C
import comps_draft_drop as DD

HALF_LIFE = 8.0
SEED = 2026
TOP_N = 240
N_TRADES = 1500
RATIO = 1.5
LIFT_BAR = 0.02
CALL_BAR = 0.020
ALPHA = 0.025
N_PERM = 10_000
TEST = (2013, 2020)
SHOW = ['Marvin Harrison Jr.', 'Makai Lemon', 'CeeDee Lamb', 'Javonte Williams', 'Caleb Williams', 'Brock Bowers',
        'Tua Tagovailoa', 'Zay Flowers', 'Michael Penix', 'Jadarian Price', 'Jaxson Dart', 'Luther Burden',
        "De'Zhaun Stribling"]


# ── setup: snapshots, neighbours (features only; no outcome is read here) ────────────────────────
def setup(nflverse, rosters):
    C.HORIZON, C.POOL_LAG = 5, 5
    st, dp, pl = C.load(nflverse, rosters)
    S, counts = C.build(st, dp, pl, snap_last=2020, extra_seasons=(2025,), check_complete=False)
    S = S.reset_index(drop=True)
    assert S[S.t <= 2020].complete.all(), 'a 2001-2020 snapshot has an unfinished five-year window'
    rows = S.index[(S.t >= TEST[0]) & (S.t <= TEST[1])].values
    pre = C.precompute(S, ks=(C.K_MAIN,), test_rows=rows)          # B1/B2/B3 bands and the 1 Nov CV neighbours
    pa = DD.neighbours(S, rows, 'A')                                # Version A neighbours (OVS)
    assert np.array_equal(pre['test'], pa['test']), 'Version A rows differ from the band rows'
    T = pre['test']
    for r, nn in zip(T, pa['nn'][30]):                              # leak checks, every row
        assert (S.t.values[nn] <= S.t.values[r] - 5).all(), 'pool leak'
        assert S.key.values[r] not in set(S.key.values[nn]), 'self in pool'
    W = []
    for r, nn in zip(T, pa['nn'][30]):
        w = 0.5 ** ((S.t.values[r] - S.t.values[nn]) / HALF_LIFE)
        W.append(w / w.sum())
    counts['test_scored'] = int(len(T)); counts['test_excluded_lt10'] = int(len(pre['excluded']))
    counts['test_players'] = int(len(set(S.key.values[T])))
    return st, S, pre, pa['nn'][30], W, counts


def predictions(S, pre, nnA, W, y):
    """Every method's prediction for every test row, from outcome vector y (pool rows only are read)."""
    return {'OVS': np.array([(w * y[nn]).sum() for nn, w in zip(nnA, W)]),
            'CV': np.array([y[nn].mean() for nn in pre['nn'][C.K_MAIN]]),
            'B1': np.array([y[m].mean() for m in pre['b1']]),
            'B2': np.array([y[m].mean() for m in pre['b2']]),
            'B3': np.array([y[m].mean() for m in pre['b3']])}


# ── trades (built from predictions only; no outcome is read) ─────────────────────────────────────
def build_trades(S, pre, p_ovs, p_b2, seed=SEED):
    """Returns (A, B, kind): A (n,1) and B (n,2) indices into the test-row array, -1 = empty slot."""
    T = pre['test']; tt = S.t.values[T]; a = (p_ovs + p_b2) / 2
    rng = np.random.default_rng(seed)
    A, B, K = [], [], []
    for t in range(TEST[0], TEST[1] + 1):
        idx = np.where(tt == t)[0]
        U = idx[np.argsort(-a[idx], kind='stable')[:TOP_N]]
        U = U[a[U] > 0]
        av = a[U]
        # one-for-one: every eligible pair, then a random 1,500
        i, j = np.triu_indices(len(U), 1)
        ok = np.maximum(av[i], av[j]) / np.minimum(av[i], av[j]) <= RATIO
        i, j = i[ok], j[ok]
        pick = rng.choice(len(i), size=min(N_TRADES, len(i)), replace=False)
        for q in pick:
            A.append([U[i[q]]]); B.append([U[j[q]], -1]); K.append(1)
        # two-for-one: random draws, kept if both are smaller and the pair is within 1.5x
        seen, tries = set(), 0
        while len(seen) < N_TRADES and tries < 400_000:
            tries += 1
            x, y1, y2 = rng.choice(len(U), 3, replace=False)
            if not (av[y1] < av[x] and av[y2] < av[x]): continue
            tot = av[y1] + av[y2]
            if max(av[x], tot) / min(av[x], tot) > RATIO: continue
            key = (x, min(y1, y2), max(y1, y2))
            if key in seen: continue
            seen.add(key)
            A.append([U[x]]); B.append([U[y1], U[y2]]); K.append(2)
    return np.array(A), np.array(B), np.array(K)


def side_sum(v, M):
    vv = np.append(v, 0.0)                                          # index -1 -> 0
    return vv[M].sum(1)


def calls(pa_, pb_, yA, yB):
    """Share-right vector: 1 right, 0 wrong, 0.5 when the method's two sides tie."""
    right = np.where(pa_ == pb_, 0.5, ((pa_ > pb_) == (yA > yB)).astype(float))
    return right


def q2(S, pre, p_ovs, p_b2, y_test, A, B, K, n_perm=N_PERM, seed=13, mask=None):
    yA, yB = side_sum(y_test, A), side_sum(y_test, B)
    ties = int((yA == yB).sum())
    keep = yA != yB
    if mask is not None: keep &= mask
    A, B, K, yA, yB = A[keep], B[keep], K[keep], yA[keep], yB[keep]
    acc = lambda p: calls(side_sum(p, A), side_sum(p, B), yA, yB)
    ro, rb = acc(p_ovs), acc(p_b2)
    obs = ro.mean() - rb.mean()
    p = None
    if n_perm:
        cl = pd.factorize(S.key.values[pre['test']])[0]; nc = cl.max() + 1
        rng = np.random.default_rng(seed); cnt = 0
        for _ in range(n_perm):
            sw = (rng.random(nc) < 0.5)[cl]
            po, pb = np.where(sw, p_b2, p_ovs), np.where(sw, p_ovs, p_b2)
            d = acc(po).mean() - acc(pb).mean()
            cnt += d >= obs - 1e-12
        p = (cnt + 1) / (n_perm + 1)
    return {'n_trades': int(keep.sum()), 'dropped_ties_all_trades': ties,
            'acc_ovs': float(ro.mean()), 'acc_b2': float(rb.mean()), 'diff': float(obs), 'p': p,
            'pass': bool(p is not None and obs >= CALL_BAR and p < ALPHA)}


def q1(S, pre, p_ovs, p_b2, y_test, n_perm=N_PERM):
    cl = S.key.values[pre['test']]
    lift, p = C.perm_test(y_test, p_ovs, p_b2, cl, n_perm)
    return {'n': int(len(y_test)), 'players': int(len(set(cl))), 'rmse_ovs': C.rmse(p_ovs, y_test),
            'rmse_b2': C.rmse(p_b2, y_test), 'lift': float(lift), 'p': float(p),
            'pass': bool(lift >= LIFT_BAR and p < ALPHA)}


def sureness(p_ovs, y_test, A, B):
    yA, yB = side_sum(y_test, A), side_sum(y_test, B)
    keep = yA != yB
    pa_, pb_ = side_sum(p_ovs, A)[keep], side_sum(p_ovs, B)[keep]
    r = np.maximum(pa_, pb_) / np.maximum(np.minimum(pa_, pb_), 1e-9)
    right = calls(pa_, pb_, yA[keep], yB[keep])
    out = {}
    for lo, hi in ((1.0, 1.10), (1.10, 1.25), (1.25, 1.50), (1.50, 99)):
        m = (r >= lo) & (r < hi)
        out[f'{lo:.2f}-{hi:.2f}'] = {'n': int(m.sum()), 'bigger_side_won': float(right[m].mean()) if m.any() else None}
    return out


def current(S, names=SHOW):
    """§8 display: 2025 snapshots on the 0-10,000 ruler, pool = snapshots through 2020."""
    rows = S.index[S.t == 2025].values
    pa = DD.neighbours(S, rows, 'A', pool_max_t=2020)
    y = S.FV.values.astype(float)
    val = {}
    for r, nn in zip(pa['test'], pa['nn'][30]):
        assert (S.t.values[nn] <= 2020).all() and S.key.values[r] not in set(S.key.values[nn])
        w = 0.5 ** ((2025 - S.t.values[nn]) / HALF_LIFE); w /= w.sum()
        val[int(r)] = float((w * y[nn]).sum())
    top = max(val.values())
    rec = lambda r: {'name': S.name.values[r], 'pos': S.pos.values[r], 'kind': S.kind.values[r],
                     'age': round(float(S.age.values[r]), 1), 'value': round(10000 * val[r] / top)}
    order = sorted(val, key=lambda r: -val[r])
    named = []
    for nm in names:
        hit = [r for r in val if str(S.name.values[r]).startswith(nm)]
        named.append(rec(hit[0]) | {'rank': order.index(hit[0]) + 1} if hit else {'name': nm, 'error': 'no 2025 snapshot'})
    return {'top25': [rec(r) | {'rank': i + 1} for i, r in enumerate(order[:25])], 'named': named,
            'n_scored': len(val)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    ap.add_argument('--counts-only', action='store_true')
    a = ap.parse_args()
    st, S, pre, nnA, W, counts = setup(a.nflverse, a.rosters)
    y = S.FV.values.astype(float)
    T = pre['test']
    # trade counts need predictions (pool outcomes only), not test outcomes
    pr = predictions(S, pre, nnA, W, y)
    A, B, K = build_trades(S, pre, pr['OVS'], pr['B2'])
    counts['trades_built'] = {'one_for_one': int((K == 1).sum()), 'two_for_one': int((K == 2).sum())}
    print(json.dumps(counts, indent=1))
    if a.counts_only:
        return
    yt = y[T]
    res = {'prereg': 'docs/PREREG-own-value-scale.md', 'counts': counts,
           'Q1': q1(S, pre, pr['OVS'], pr['B2'], yt), 'Q2': q2(S, pre, pr['OVS'], pr['B2'], yt, A, B, K)}
    cy = S.cy.values[T]; kind = S.kind.values[T]
    sideA_cy = np.append(cy, -1)[A]; sideB_cy = np.append(cy, -1)[B]
    youngA = (sideA_cy[:, 0] <= 2); oldA = sideA_cy[:, 0] >= 5
    youngB = ((sideB_cy >= 0) & (sideB_cy <= 2)).any(1); oldB = np.where(B >= 0, sideB_cy >= 5, True).all(1)
    yo = (youngA & oldB) | (oldA & youngB)
    rook = (np.append(kind == 'R0', False)[A].any(1)) | (np.append(kind == 'R0', False)[B].any(1))
    res['Q2_breakdown'] = {
        'one_for_one': q2(S, pre, pr['OVS'], pr['B2'], yt, A, B, K, n_perm=0, mask=K == 1),
        'two_for_one': q2(S, pre, pr['OVS'], pr['B2'], yt, A, B, K, n_perm=0, mask=K == 2),
        'young_vs_old': q2(S, pre, pr['OVS'], pr['B2'], yt, A, B, K, n_perm=0, mask=yo),
        'with_a_rookie': q2(S, pre, pr['OVS'], pr['B2'], yt, A, B, K, n_perm=0, mask=rook)}
    pos = S.pos.values[T]
    for p in C.POS:
        res['Q2_breakdown'][f'single_side_{p}'] = q2(S, pre, pr['OVS'], pr['B2'], yt, A, B, K, n_perm=0,
                                                    mask=pos[A[:, 0]] == p)
    res['sureness_ovs'] = sureness(pr['OVS'], yt, A, B)
    res['breakdown'] = C.breakdown(S, pre, pr, y)
    res['current_players'] = current(S)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'own_value_scale_results.json')
    json.dump(res, open(out, 'w'), indent=1, default=float)
    print(json.dumps({k: res[k] for k in ('Q1', 'Q2')}, indent=1, default=float))


if __name__ == '__main__':
    main()
