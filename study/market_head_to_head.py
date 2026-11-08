#!/usr/bin/env python3
"""
DELTA — MARKET VS DELTA, HEAD TO HEAD, BY POSITION. Implements docs/PREREG-market-head-to-head.md.

Market: Fantasy Football Calculator dynasty ADP (12-team mock drafts, late summer of year Y; 1QB), 2015-2023.
DELTA:  the adopted offseason Own Value Scale (era-adjusted matching, three seasons ahead; ovs_era.py), snapshot
        t = Y - 1 (the offseason before Y). Incoming rookies use their draft-day snapshot.
Truth:  what each player produced over seasons Y..Y+2 (FV3, 12-team superflex lines, half PPR + TE premium).
Within each year and position, every pair of players whose outcomes differ: which method ordered them right?

    python market_head_to_head.py --nflverse D --rosters D --counts-only
    python market_head_to_head.py --nflverse D --rosters D --crash [--runs 100]
    python market_head_to_head.py --nflverse D --rosters D --run
"""
import argparse, glob, json, os, re
import numpy as np
import pandas as pd
import comps_value_study as C
import ovs_era as E

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YEARS = range(2015, 2024)          # Y; outcome Y..Y+2 must be finished (<= 2025)
N_BOOT = 4000
LEVEL = 1 - 0.05 / 4               # four positions decide: 98.75% ranges
SEED = 20261108
OUT = os.path.join(ROOT, 'study', 'out')


def norm(s):
    s = re.sub(r"[.'’]", '', str(s).lower()); s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', s)
    return re.sub(r'[^a-z]', '', s)


def market_rows():
    rows = []
    for y in YEARS:
        d = json.load(open(os.path.join(ROOT, 'data', 'fixtures', f'ffc-dynasty-adp-{y}.json')))['response']
        for p in d['players']:
            if p['position'] in C.POS:
                rows.append({'Y': y, 'name': p['name'], 'pos': p['position'], 'adp': float(p['adp'])})
    return pd.DataFrame(rows)


def setup(nflverse, rosters):
    st, S, S2, pre, nnA, W, nn2, W2, counts = E.setup(nflverse, rosters)    # the adopted offseason value
    y = S.FV.values.astype(float); T = pre['test']
    pe = E.preds(nn2, W2, y)
    snap = pd.DataFrame({'key': S.key.values[T], 't': S.t.values[T], 'pos': S.pos.values[T], 'kind': S.kind.values[T],
                         'name': S.name.values[T], 'delta': pe, 'fv': y[T]})
    # names each snapshot player is known by (nflverse players file), for matching FFC's spelling
    pp = pd.read_csv(os.path.join(nflverse, 'players.csv'), low_memory=False)
    alias = {}
    for r in pp.itertuples():
        nm = {r.display_name} | {f'{f} {r.last_name}' for f in (r.first_name, r.football_name, r.common_first_name) if isinstance(f, str)}
        alias[r.gsis_id] = {norm(x) for x in nm if isinstance(x, str)}
    idx = {}
    for i, (k, t, ps, nm) in enumerate(zip(snap.key, snap.t, snap.pos, snap.name)):
        for n in {norm(nm)} | alias.get(k, set()):
            idx.setdefault((int(t), ps, n), set()).add(i)
    M = market_rows()
    hit, amb, miss = [], 0, []
    for r in M.itertuples():
        h = idx.get((r.Y - 1, r.pos, norm(r.name)), set())
        if len(h) == 1: hit.append((r.Index, h.pop()))
        elif len(h) > 1: amb += 1
        else: miss.append(f'{r.Y} {r.name} {r.pos}')
    mi, si = zip(*hit)
    D = M.loc[list(mi)].reset_index(drop=True).join(snap.iloc[list(si)].reset_index(drop=True)[['key', 'kind', 'delta', 'fv']])
    assert not D.duplicated(['Y', 'key']).any()
    counts = {'market_rows': int(len(M)), 'matched': int(len(D)), 'ambiguous': amb, 'unmatched': len(miss),
              'unmatched_examples': miss[:25], 'matched_by_position': D.pos.value_counts().to_dict(),
              'matched_rookies': int((D.kind == 'R0').sum())}
    return D, counts


def pairs(D):
    """All within-(year, position) pairs whose outcomes differ: (i, j, position) with fv_i > fv_j."""
    I, J, P = [], [], []
    for (y, ps), g in D.groupby(['Y', 'pos']):
        ix = g.index.values; f = g.fv.values
        a, b = np.triu_indices(len(ix), 1)
        keep = f[a] != f[b]
        a, b = a[keep], b[keep]
        hi = np.where(f[a] > f[b], a, b); lo = np.where(f[a] > f[b], b, a)
        I.append(ix[hi]); J.append(ix[lo]); P += [ps] * len(hi)
    return np.concatenate(I), np.concatenate(J), np.array(P)


def right(D, I, J, fv=None):
    """Per pair: market right (earlier ADP = better), DELTA right (higher value), ties count half."""
    adp, dv = D.adp.values, D.delta.values
    m = np.where(adp[I] < adp[J], 1.0, np.where(adp[I] == adp[J], 0.5, 0.0))
    d = np.where(dv[I] > dv[J], 1.0, np.where(dv[I] == dv[J], 0.5, 0.0))
    return m, d


def compare(D, I, J, P, n_boot=N_BOOT, seed=SEED):
    m, d = right(D, I, J)
    keys = D.key.values; u, inv = np.unique(keys, return_inverse=True)
    rng = np.random.default_rng(seed); out = {}
    for ps in list(C.POS) + ['ALL']:
        sel = np.ones(len(I), bool) if ps == 'ALL' else (P == ps)
        mi, di = m[sel], d[sel]; ii, jj = inv[I[sel]], inv[J[sel]]
        diffs = []
        for _ in range(n_boot):                 # resample players; a pair counts (count_i x count_j) times
            c = np.bincount(rng.integers(0, len(u), len(u)), minlength=len(u)).astype(float)
            w = c[ii] * c[jj]
            if w.sum() == 0: continue
            diffs.append(((mi - di) * w).sum() / w.sum())
        lo, hi = np.quantile(diffs, [(1 - LEVEL) / 2, 1 - (1 - LEVEL) / 2])
        verdict = 'market better' if lo > 0 else ('DELTA better' if hi < 0 else 'no clear winner')
        out[ps] = {'pairs': int(sel.sum()), 'market_right': float(mi.mean()), 'delta_right': float(di.mean()),
                   'diff': float(mi.mean() - di.mean()), 'range': [float(lo), float(hi)], 'verdict': verdict}
    return out


def crash(D, I, J, P, runs):
    """Synthetic outcomes from each method's within-group standing; checks the verdict machinery only."""
    z = lambda v: (v - v.mean()) / (v.std() or 1)
    zm = np.zeros(len(D)); zd = np.zeros(len(D))
    for _, g in D.groupby(['Y', 'pos']):
        zm[g.index] = z(-g.adp.rank().values); zd[g.index] = z(g.delta.rank().values)
    res = {}
    for w, key, want in ((0.5, 'tie', 'no clear winner'), (0.75, 'market_planted', 'market better'), (0.25, 'delta_planted', 'DELTA better')):
        rng = np.random.default_rng(int(w * 100)); hits = {ps: 0 for ps in list(C.POS) + ['ALL']}; acc = []
        for r in range(runs):
            fv = w * zm + (1 - w) * zd + rng.normal(0, 1.0, len(D))
            D2 = D.copy(); D2['fv'] = fv
            I2, J2, P2 = pairs(D2)
            out = compare(D2, I2, J2, P2, n_boot=500, seed=r)
            for ps in hits: hits[ps] += out[ps]['verdict'] == want
            acc.append(out['ALL']['market_right'])
        res[key] = {'runs': runs, 'right_verdict': hits, 'typical_market_right': float(np.median(acc))}
        print(key, res[key], flush=True)
    res['ok'] = all(v >= 0.95 * runs for v in res['tie']['right_verdict'].values()) and \
        all(res[k]['right_verdict'][ps] >= 0.8 * runs for k in ('market_planted', 'delta_planted') for ps in ('RB', 'TE'))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--counts-only', action='store_true'); g.add_argument('--crash', action='store_true')
    g.add_argument('--run', action='store_true')
    ap.add_argument('--runs', type=int, default=100)
    a = ap.parse_args()
    D, counts = setup(a.nflverse, a.rosters)
    I, J, P = pairs(D)
    counts['pairs_by_position'] = {ps: int((P == ps).sum()) for ps in C.POS}
    print(json.dumps(counts, indent=1, default=int))
    if a.counts_only: return
    if a.crash:
        res = crash(D, I, J, P, a.runs); res['counts'] = counts
        json.dump(res, open(os.path.join(OUT, 'market_h2h_crash.json'), 'w'), indent=1, default=float)
        print('crash tests:', 'PASS' if res['ok'] else 'FAIL'); return
    res = {'prereg': 'docs/PREREG-market-head-to-head.md', 'counts': counts, 'by_position': compare(D, I, J, P)}
    # reported only: young players (age unknown here) -> rookies vs veterans; each year
    res['rookies_vs_veterans'] = {}
    for kd in ('R0', 'V'):
        sel = (D.kind.values[I] == kd) & (D.kind.values[J] == kd)
        m, d = right(D, I[sel], J[sel])
        res['rookies_vs_veterans'][kd] = {'pairs': int(sel.sum()), 'market_right': float(m.mean()), 'delta_right': float(d.mean())}
    res['by_year'] = {}
    for y in YEARS:
        sel = D.Y.values[I] == y; m, d = right(D, I[sel], J[sel])
        res['by_year'][y] = {'pairs': int(sel.sum()), 'market_right': float(m.mean()), 'delta_right': float(d.mean())}
    json.dump(res, open(os.path.join(OUT, 'market_h2h_results.json'), 'w'), indent=1, default=float)
    print(json.dumps(res['by_position'], indent=1))


if __name__ == '__main__':
    main()
