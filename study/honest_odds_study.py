#!/usr/bin/env python3
"""
DELTA — MAKING "PLAYERS LIKE HIM" ODDS HONEST

Implements docs/PREREG-honest-odds.md. Where the two disagree, the pre-registration (with its section 9
amendments) wins.

Three versions of the comparables odds, same 30 comparables as the 1 Nov method, three-season horizon:
  As-is   plain share / average of the 30
  Fix 1   League Size: each comparable's result scaled by N(s,pos)/N(t,pos), capped at 1
  Fix 2   Recent Count More: comparable weighted 0.5 ** ((t - s) / 8)
  (Both   reported only)
Numbers: P3 = chance of >= 1 starter season in the next three; E3 = expected starter seasons in the next three.
Graded on FRESH snapshots t = 2021, 2022 (never graded before). Seen-data check t = 2013-2020, reported only.

Usage:
    python honest_odds_study.py --nflverse DIR --rosters DIR --counts-only
    python honest_odds_study.py --nflverse DIR --rosters DIR          # confirmatory (once, after lock)
"""
import argparse, json, os
import numpy as np
import comps_value_study as C

H = 3
FRESH = (2021, 2022)
SEEN = tuple(range(2013, 2021))
HALF_LIFE = 8.0
BRIER_GUARD = 1.01
N_SIM = 2000
POS_PCT = 100 * (1 - 0.05 / 8)
VERSIONS = ('As-is', 'Fix 1', 'Fix 2', 'Both')
DECIDING = ('As-is', 'Fix 1', 'Fix 2')


def setup(nflverse, rosters):
    C.HORIZON, C.POOL_LAG = H, H
    st, dp, pl = C.load(nflverse, rosters)
    S, cnt = C.build(st, dp, pl, snap_last=max(FRESH))
    S = S.reset_index(drop=True)
    g = st[st.games >= 1].groupby(['season', 'position']).size()
    N = {(int(s), p): int(n) for (s, p), n in g.items()}
    return S, N, cnt


def comps(S, years):
    rows = S.index[S.t.isin(years)].values
    pre = C.precompute(S, ks=(C.K_MAIN,), test_rows=rows)
    for r, nn in zip(pre['test'], pre['nn'][C.K_MAIN]):
        assert (S.t.values[nn] <= S.t.values[r] - H).all(), 'pool leak'
        assert S.key.values[r] not in set(S.key.values[nn]), 'self in pool'
    return pre


def version_parts(S, N, pre, version):
    """Per row: (comparable indices, normalized weights, thinning ratio r in [0,1])."""
    out = []
    t_all = S.t.values; pos = S.pos.values
    for r, nn in zip(pre['test'], pre['nn'][C.K_MAIN]):
        t = t_all[r]; s = t_all[nn]
        w = np.ones(len(nn))
        if version in ('Fix 2', 'Both'):
            w = 0.5 ** ((t - s) / HALF_LIFE)
        w = w / w.sum()
        ratio = np.ones(len(nn))
        if version in ('Fix 1', 'Both'):
            Nt = N[(int(t), pos[r])]
            ratio = np.minimum(1.0, np.array([N[(int(x), pos[r])] for x in s]) / Nt)
        out.append((nn, w, ratio))
    return out


def predictions(S, parts):
    hit = S.any_start.values.astype(float); cnt = S.n_start.values.astype(float)
    P = np.array([min(1.0, (w * hit[nn] * r).sum()) for nn, w, r in parts])
    E = np.array([(w * cnt[nn] * r).sum() for nn, w, r in parts])
    return P, E


def edges_for(pred, measure):
    if measure == 'P3':
        e = np.linspace(0, 1, 11)
    else:
        e = np.unique(np.quantile(pred, np.linspace(0, 1, 11)))
    e = e.astype(float); e[-1] += 1e-9
    return e


def pad(S, parts):
    """Comparables as (rows x k) matrices: cumulative weights, starter-season counts, thinning ratios."""
    k = max(len(nn) for nn, _, _ in parts)
    cnt = S.n_start.values.astype(int)
    CW = np.ones((len(parts), k)); CNT = np.zeros((len(parts), k), int); R = np.ones((len(parts), k))
    for i, (nn, w, r) in enumerate(parts):
        CW[i, :len(nn)] = np.cumsum(w); CNT[i, :len(nn)] = cnt[nn]; R[i, :len(nn)] = r
    return CW, CNT, R


def draw_counts(rng, CW, CNT, R):
    """One honest draw per row: pick a comparable by weight, thin his starter seasons by his ratio."""
    u = rng.random(len(CW))
    j = np.minimum((CW < u[:, None]).sum(1), CW.shape[1] - 1)
    i = np.arange(len(CW))
    return rng.binomial(CNT[i, j], R[i, j]).astype(float)


def sim_limits(S, parts, P, E, masks, n_sim=N_SIM, seed=5):
    """Honest-forecaster calibration errors (depend only on the forecasts, not on outcomes).
    P3: Bernoulli(P). E3: draw a comparable by weight, thin his starter seasons by his ratio."""
    rng = np.random.default_rng(seed)
    cnt = S.n_start.values.astype(int)
    n = len(P)
    sims = {(g, m): np.empty(n_sim) for g in masks for m in ('P3', 'E3')}
    edges = {(g, m): edges_for((P if m == 'P3' else E)[mk], m) for g, mk in masks.items() for m in ('P3', 'E3')}
    CW, CNT, R = pad(S, parts)
    for k in range(n_sim):
        yp = (rng.random(n) < P).astype(float)
        ye = draw_counts(rng, CW, CNT, R)
        for g, mk in masks.items():
            sims[(g, 'P3')][k] = C.calib_error(P[mk], yp[mk], edges[(g, 'P3')])[0]
            sims[(g, 'E3')][k] = C.calib_error(E[mk], ye[mk], edges[(g, 'E3')])[0]
    return sims, edges


def masks_for(S, pre):
    pos = S.pos.values[pre['test']]
    m = {'overall': np.ones(len(pre['test']), bool)}
    for p in C.POS:
        m[p] = pos == p
    return m


def judge(P, E, yP, yE, masks, sims, edges):
    """The 1 Nov A6 rule: overall at the 95th percentile, every position at the 99.375th."""
    checks, ok = {}, True
    for g, mk in masks.items():
        pct = 95.0 if g == 'overall' else POS_PCT
        for m, pred, obs in (('P3', P, yP), ('E3', E, yE)):
            err, tab = C.calib_error(pred[mk], obs[mk], edges[(g, m)])
            lim = float(np.percentile(sims[(g, m)], pct))
            checks[f'{g} {m}'] = {'n': int(mk.sum()), 'error': float(err), 'limit': lim, 'honest': bool(err <= lim),
                                  'table': tab if g == 'overall' else None}
            ok &= err <= lim
    return bool(ok), checks


def brier(P, y): return float(np.mean((P - y) ** 2))


def run(S, N, years, n_sim=N_SIM):
    pre = comps(S, years)
    masks = masks_for(S, pre)
    T = pre['test']
    yP = S.any_start.values[T].astype(float); yE = S.n_start.values[T].astype(float)
    out = {'n': int(len(T)), 'players': int(len(set(S.key.values[T]))),
           'by_kind': {k: int((S.kind.values[T] == k).sum()) for k in ('V', 'R0')}, 'versions': {}}
    for v in VERSIONS:
        parts = version_parts(S, N, pre, v)
        P, E = predictions(S, parts)
        sims, edges = sim_limits(S, parts, P, E, masks, n_sim)
        honest, checks = judge(P, E, yP, yE, masks, sims, edges)
        kind = S.kind.values[T]
        out['versions'][v] = {'honest': honest, 'brier': brier(P, yP), 'checks': checks,
                              'said_vs_happened': {k: {'said': float(P[kind == k].mean()), 'happened': float(yP[kind == k].mean())}
                                                   for k in ('V', 'R0')}}
    base = out['versions']['As-is']['brier']
    for v in VERSIONS:
        out['versions'][v]['guard_ok'] = bool(out['versions'][v]['brier'] <= BRIER_GUARD * base)
    return out


def choose(res):
    v = res['versions']
    if v['As-is']['honest']:
        return 'As-is'
    ok = [x for x in ('Fix 1', 'Fix 2') if v[x]['honest'] and v[x]['guard_ok']]
    if not ok:
        return None
    return min(ok, key=lambda x: v[x]['brier'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    ap.add_argument('--counts-only', action='store_true')
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out',
                                                 'honest_odds_results.json'))
    a = ap.parse_args()
    S, N, cnt = setup(a.nflverse, a.rosters)
    fresh = S[S.t.isin(FRESH)]
    print(json.dumps({'fresh_rows': int(len(fresh)), 'fresh_by_kind': fresh.groupby('kind').size().to_dict(),
                      'fresh_by_pos': fresh.groupby('pos').size().to_dict(),
                      'N_examples': {f'{s} {p}': N[(s, p)] for s in (2001, 2010, 2018, 2021, 2022) for p in C.POS}},
                     indent=1, default=int))
    if a.counts_only:
        return
    res = {'prereg': 'docs/PREREG-honest-odds.md', 'fresh': run(S, N, FRESH)}
    res['decision'] = choose(res['fresh'])
    res['seen_2013_2020_reported_only'] = run(S, N, SEEN, n_sim=500)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w') as f:
        json.dump(res, f, indent=1, default=float)
    print('decision:', res['decision'])
    for v, x in res['fresh']['versions'].items():
        print(v, 'honest', x['honest'], 'brier', round(x['brier'], 4), 'guard', x['guard_ok'], x['said_vs_happened'])


if __name__ == '__main__':
    main()
