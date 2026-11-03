#!/usr/bin/env python3
"""
DELTA — COMPARABLES: DROP DRAFT SLOT AFTER TWO SEASONS. Implements docs/PREREG-draft-drop.md.
Reuses comps_draft_weight.py's neighbour code (locked ee43651) with a weight hook that also sees career year.

    python comps_draft_drop.py --nflverse DIR --rosters DIR
"""
import argparse, json, os
import numpy as np
import comps_value_study as C
import honest_odds_study as O
import comps_draft_weight as DW

CUT = {'A': 2, 'B': 3}


def install(mode):
    """Point comps_draft_weight's weight function at `mode` (today / A / B) using career year from the caller's rows."""
    def w(_, G, n, cy=None):
        base = DW.weights('today', G, n)
        if mode in CUT:
            base = base.copy(); base[cy >= CUT[mode], 2] = 0.0
        return base
    return w


def neighbours(S, rows, mode, pool_max_t=None):
    """Same construction as DW.neighbours; the veteran weight call also gets that block's career years."""
    orig = DW.weights
    _current_cy.clear()
    DW.weights = lambda m, G, n: install(mode)(m, G, n, cy=_current_cy.pop(0))
    try:
        return _neighbours_tracking(S, rows, mode, pool_max_t)
    finally:
        DW.weights = orig


_current_cy = []


def _neighbours_tracking(S, rows, mode, pool_max_t):
    """Re-implements DW.neighbours' loop only to queue each veteran block's career years before DW's weight call."""
    keys = S.key.values; tt = S.t.values; pos = S.pos.values; kind = S.kind.values
    out_rows, out_nn = [], []
    for t in sorted(set(tt[rows])):
        pmax = t - C.POOL_LAG if pool_max_t is None else pool_max_t
        pool_all = S.index[(S.t >= C.SNAP_FIRST) & (S.t <= pmax)].values
        rows_t = rows[tt[rows] == t]
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
                    _current_cy.append(S.cy.values[trow])
                    W = DW.weights('x', S.loc[trow, 'G'].values.astype(float), len(trow))
                else:
                    W = np.tile([C.W_R0['draft'], C.W_R0['age']], (len(trow), 1))
                d2 = (((Tz[:, None, :] - Pz[None, :, :]) ** 2) * W[:, None, :]).sum(2)
                for i, r in enumerate(trow):
                    same = keys[prow] == keys[r]
                    dd = d2[i].copy(); dd[same] = np.inf
                    n_avail = int((~same).sum())
                    if n_avail < C.K_MIN: continue
                    nn = prow[np.argsort(dd, kind='stable')[:min(30, n_avail)]]
                    assert keys[r] not in set(keys[nn]) and (tt[nn] <= pmax).all()
                    out_rows.append(r); out_nn.append(nn)
    return {'test': np.array(out_rows, dtype=int), 'nn': {30: out_nn}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--nflverse', required=True); ap.add_argument('--rosters', required=True)
    a = ap.parse_args()
    res = {'prereg': 'docs/PREREG-draft-drop.md'}
    # equivalence: 'today' through this hook == precompute
    S5, _ = DW.build(a, 5, 2020)
    rows5 = S5.index[(S5.t >= 2013) & (S5.t <= 2020)].values
    ref = C.precompute(S5, ks=(30,), test_rows=rows5)
    mine = neighbours(S5, rows5, 'today')
    bad = sum(not np.array_equal(x, y) for x, y in zip(ref['nn'][30], mine['nn'][30]))
    assert np.array_equal(ref['test'], mine['test']) and bad == 0, f'equivalence failed: {bad}'
    res['equivalence_mismatches'] = bad
    y = S5.FV.values.astype(float)
    preds = {m: np.array([y[nn].mean() for nn in neighbours(S5, rows5, m)['nn'][30]]) for m in ('today', 'A', 'B')}
    T = mine['test']; yt = y[T]; cl = S5.key.values[T]; cy = S5.cy.values[T]; vet = S5.kind.values[T] == 'V'
    S3, N = DW.build(a, 3, 2022)
    for m in ('A', 'B'):
        q = {}
        for g, mk in (('all', np.ones(len(T), bool)), ('changed_veterans', vet & (cy >= CUT[m]))):
            r0, r1 = C.rmse(preds['today'][mk], yt[mk]), C.rmse(preds[m][mk], yt[mk])
            lift, p = C.perm_test(yt[mk], preds[m][mk], preds['today'][mk], cl[mk])
            q[g] = {'n': int(mk.sum()), 'rmse_today': r0, 'rmse_new': r1, 'ratio': r1 / r0, 'p_new_better': p}
        q['Q1_pass'] = bool(q['all']['ratio'] <= 1.01 and q['changed_veterans']['ratio'] <= 1.01)
        odds = {}
        for years, lab in (((2021, 2022), 'fresh_2021_2022'), ((2009, 2010, 2011, 2012), 'report_2009_2012')):
            rows = S3.index[S3.t.isin(list(years))].values
            pre = neighbours(S3, rows, m)
            masks = O.masks_for(S3, pre); TT = pre['test']
            parts = O.version_parts(S3, N, pre, 'Fix 2'); P, E = O.predictions(S3, parts)
            sims, edges = O.sim_limits(S3, parts, P, E, masks)
            yP = S3.any_start.values[TT].astype(float); yE = S3.n_start.values[TT].astype(float)
            h, ch = O.judge(P, E, yP, yE, masks, sims, edges)
            odds[lab] = {'honest': h, 'brier': O.brier(P, yP), 'failed_checks': [k for k, v in ch.items() if not v['honest']]}
        q['odds'] = odds; q['Q2_pass'] = odds['fresh_2021_2022']['honest']
        q['pass'] = q['Q1_pass'] and q['Q2_pass']
        res[m] = q
    res['decision'] = 'A' if res['A']['pass'] else ('B' if res['B']['pass'] else 'keep today')
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'comps_draft_drop_results.json'), 'w'),
              indent=1, default=float)
    print(json.dumps(res, indent=1, default=float))


if __name__ == '__main__':
    main()
