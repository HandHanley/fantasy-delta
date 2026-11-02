#!/usr/bin/env python3
"""
DELTA — COMPARABLES: GIVE DRAFT SLOT THE WEIGHT K = 24 IMPLIES

Implements docs/PREREG-draft-weight.md. Reuses comps_value_study.py and honest_odds_study.py (both locked) unchanged.

    python comps_draft_weight.py --nflverse DIR --rosters DIR --check     # equivalence check only
    python comps_draft_weight.py --nflverse DIR --rosters DIR             # real run (once, after lock)
"""
import argparse, json, os
import numpy as np
import comps_value_study as C
import honest_odds_study as O

K = 24.0


def weights(mode, G, n):
    if mode == 'today':
        return np.stack([np.full(n, C.W_V['prod']), np.full(n, C.W_V['age']), C.W_V['draft'] * C.K_FADE / (G + C.K_FADE),
                         np.full(n, C.W_V['cy']), np.full(n, C.W_V['games'])], 1)
    if mode == 'k24':
        return np.stack([3.0 * G / (G + K), np.full(n, 2.0), 3.0 * K / (G + K), np.full(n, 1.0), np.full(n, 1.0)], 1)
    raise ValueError(mode)


def neighbours(S, test_rows, mode, k=30, pool_max_t=None):
    """CV neighbours, same construction as comps_value_study.precompute, veteran weights by `mode`.
    Returns {'test': rows kept, 'nn': {k: [arrays]}} in the order precompute uses."""
    keys = S.key.values; tt = S.t.values; pos = S.pos.values; kind = S.kind.values
    out_rows, out_nn = [], []
    for t in sorted(set(tt[test_rows])):
        pmax = t - C.POOL_LAG if pool_max_t is None else pool_max_t
        pool_all = S.index[(S.t >= C.SNAP_FIRST) & (S.t <= pmax)].values
        rows_t = test_rows[tt[test_rows] == t]
        for p in C.POS:
            for kd in ('V', 'R0'):
                trow = rows_t[(pos[rows_t] == p) & (kind[rows_t] == kd)]
                if not len(trow): continue
                prow = pool_all[(pos[pool_all] == p) & (kind[pool_all] == kd)]
                feats = ['prod', 'age', 'draft', 'cy', 'games'] if kd == 'V' else ['draft', 'age']
                P = S.loc[prow, feats].values.astype(float)
                mu, sd = P.mean(0), P.std(0); sd[sd == 0] = 1.0
                Pz = (P - mu) / sd; Tz = (S.loc[trow, feats].values.astype(float) - mu) / sd
                if kd == 'V':
                    W = weights(mode, S.loc[trow, 'G'].values.astype(float), len(trow))
                else:
                    W = np.tile([C.W_R0['draft'], C.W_R0['age']], (len(trow), 1))
                d2 = (((Tz[:, None, :] - Pz[None, :, :]) ** 2) * W[:, None, :]).sum(2)
                for i, r in enumerate(trow):
                    same = keys[prow] == keys[r]
                    dd = d2[i].copy(); dd[same] = np.inf
                    n_avail = int((~same).sum())
                    if n_avail < C.K_MIN: continue
                    nn = prow[np.argsort(dd, kind='stable')[:min(k, n_avail)]]
                    assert keys[r] not in set(keys[nn]), 'self in neighbours'
                    assert (tt[nn] <= pmax).all(), 'pool leak'
                    out_rows.append(r); out_nn.append(nn)
    return {'test': np.array(out_rows, dtype=int), 'nn': {k: out_nn}}


def build(a, horizon, snap_last, extra=()):
    C.HORIZON, C.POOL_LAG = horizon, horizon
    st, dp, pl = C.load(a.nflverse, a.rosters)
    S, cnt = C.build(st, dp, pl, snap_last=snap_last, extra_seasons=extra, check_complete=not extra)
    S = S.reset_index(drop=True)
    g = st[st.games >= 1].groupby(['season', 'position']).size()
    N = {(int(s), p): int(n) for (s, p), n in g.items()}
    return S, N


def equivalence(a):
    """Today's weights through this code must give precompute's neighbours exactly (5-year and 3-year)."""
    out = {}
    for horizon, snap_last, years in ((5, 2020, range(2013, 2021)), (3, 2022, (2021, 2022))):
        S, _ = build(a, horizon, snap_last)
        rows = S.index[S.t.isin(list(years))].values
        ref = C.precompute(S, ks=(30,), test_rows=rows)
        mine = neighbours(S, rows, 'today')
        assert np.array_equal(ref['test'], mine['test']), 'row order differs'
        bad = sum(not np.array_equal(x, y) for x, y in zip(ref['nn'][30], mine['nn'][30]))
        out[f'horizon{horizon}'] = {'rows': int(len(rows)), 'mismatched_rows': int(bad)}
        assert bad == 0, f'{bad} rows differ'
    return out


def q1(a):
    S, _ = build(a, 5, 2020)
    rows = S.index[(S.t >= C.TEST_FIRST) & (S.t <= C.TEST_LAST)].values
    y = S.FV.values.astype(float)
    res = {}
    preds = {}
    for mode in ('today', 'k24'):
        pre = neighbours(S, rows, mode)
        if mode == 'today': T0 = pre['test']
        assert np.array_equal(pre['test'], T0), 'different rows'
        preds[mode] = np.array([y[nn].mean() for nn in pre['nn'][30]]); T = pre['test']
    yt = y[T]; cl = S.key.values[T]; cy = S.cy.values[T]; kind = S.kind.values[T]
    groups = {'all': np.ones(len(T), bool), 'veterans_years_1_3': (kind == 'V') & (cy <= 3),
              'veterans_years_4_plus': (kind == 'V') & (cy >= 4), 'rookies': kind == 'R0'}
    for g, m in groups.items():
        r0, r1 = C.rmse(preds['today'][m], yt[m]), C.rmse(preds['k24'][m], yt[m])
        lift, p = C.perm_test(yt[m], preds['k24'][m], preds['today'][m], cl[m])
        rng = np.random.default_rng(3); uc = np.unique(cl[m]); ratios = []
        idx = {c: np.flatnonzero(cl[m] == c) for c in uc}
        for _ in range(1000):
            take = np.concatenate([idx[c] for c in rng.choice(uc, len(uc))])
            ratios.append(C.rmse(preds['k24'][m][take], yt[m][take]) / C.rmse(preds['today'][m][take], yt[m][take]))
        res[g] = {'n': int(m.sum()), 'rmse_today': r0, 'rmse_k24': r1, 'ratio': r1 / r0, 'lift': lift, 'p_k24_better': p,
                  'ratio_95_range': [float(np.percentile(ratios, 2.5)), float(np.percentile(ratios, 97.5))],
                  'mae_today': C.mae(preds['today'][m], yt[m]), 'mae_k24': C.mae(preds['k24'][m], yt[m]),
                  'spearman_today': C.spearman(preds['today'][m], yt[m]), 'spearman_k24': C.spearman(preds['k24'][m], yt[m])}
    res['pass'] = bool(res['all']['ratio'] <= 1.01 and res['veterans_years_1_3']['ratio'] <= 1.01)
    return res


def q2(a):
    S, N = build(a, 3, 2022)
    out = {}
    for years, label in (((2021, 2022), 'fresh_2021_2022'), ((2009, 2010, 2011, 2012), 'report_2009_2012')):
        rows = S.index[S.t.isin(list(years))].values
        pre = neighbours(S, rows, 'k24')
        masks = O.masks_for(S, pre); T = pre['test']
        parts = O.version_parts(S, N, pre, 'Fix 2')
        P, E = O.predictions(S, parts)
        sims, edges = O.sim_limits(S, parts, P, E, masks)
        yP = S.any_start.values[T].astype(float); yE = S.n_start.values[T].astype(float)
        honest, checks = O.judge(P, E, yP, yE, masks, sims, edges)
        kind = S.kind.values[T]
        out[label] = {'honest': honest, 'brier': O.brier(P, yP),
                      'checks': {k: {x: v[x] for x in ('error', 'limit', 'honest')} for k, v in checks.items()},
                      'said_vs_happened': {k: {'said': float(P[kind == k].mean()), 'happened': float(yP[kind == k].mean())}
                                           for k in ('V', 'R0')}}
    out['pass'] = out['fresh_2021_2022']['honest']
    return out


def display(a):
    S, _ = build(a, 3, 2022, extra=(2025,))
    out = {}
    for nm in ('Marvin Harrison Jr.', 'CeeDee Lamb', 'Brock Bowers', 'Javonte Williams'):
        r = int(S[(S.t == 2025) & (S.name == nm)].index[0])
        out[nm] = {}
        for mode in ('today', 'k24'):
            nn = neighbours(S, np.array([r]), mode, pool_max_t=2022)['nn'][30][0]
            pk = S.pick.values[nn]
            out[nm][mode] = {'pick_range': [int(pk.min()), int(pk.max())], 'picks_65_plus': int((pk > 64).sum()),
                             'names_65_plus': sorted({S.name.values[i] for i in nn if S.pick.values[i] > 64})}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    eq = equivalence(a)
    print('equivalence', eq, flush=True)
    if a.check:
        return
    res = {'prereg': 'docs/PREREG-draft-weight.md', 'equivalence': eq, 'Q1': q1(a), 'Q2': q2(a), 'display': display(a)}
    res['decision'] = 'switch to K=24 version' if res['Q1']['pass'] and res['Q2']['pass'] else 'keep today'
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'comps_draft_weight_results.json')
    json.dump(res, open(path, 'w'), indent=1, default=float)
    print(json.dumps({'Q1': {g: {k: v for k, v in x.items()} if isinstance(x, dict) else x for g, x in res['Q1'].items()},
                      'Q2': {k: (v if not isinstance(v, dict) else {x: v[x] for x in ('honest', 'brier', 'said_vs_happened')})
                             for k, v in res['Q2'].items()},
                      'display': res['display'], 'decision': res['decision']}, indent=1, default=float))


if __name__ == '__main__':
    main()
