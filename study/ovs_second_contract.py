#!/usr/bin/env python3
"""
DELTA — OWN VALUE SCALE: THE SECOND-CONTRACT MOMENT. Implements docs/PREREG-ovs-second-contract.md.

Base: the adopted preseason value (offseason features, games out of matching). For a drafted player at the end of the
four guaranteed years of his rookie deal (snapshot season t = draft year + 3), his club entering t+1 is one of
  kept   same club as his last club of season t        moved  another club        none  no club in weeks 1-5
His value is scaled by his group's history: sum of outcomes / sum of base values over end-of-deal rows with t' <= t - 3
(results already in), all positions together; a group with fewer than N_MIN such rows is left unscaled.

    python ovs_second_contract.py --nflverse D --rosters D --week1 FILE --counts-only | --crash | --run
"""
import argparse, glob, json, os
import numpy as np, pandas as pd
import comps_value_study as C
import ovs_era as E
import ovs_offseason as O
import own_value_scale as V

N_MIN = 30
LIFT_BAR, ALPHA, ALL_GUARD = 0.02, 0.05, -0.005
FRANCHISE = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}          # a relocated club is the same club
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')


def club(code):
    c = O.CANON.get(code, code)
    return FRANCHISE.get(c, c)


def groups(S, nflverse, rosters, week1):
    dp = pd.read_csv(os.path.join(nflverse, 'draft_picks.csv'), low_memory=False)
    dp = dp[dp.gsis_id.notna()].sort_values(['season', 'pick']).drop_duplicates('gsis_id')
    dyear = dict(zip(dp.gsis_id, dp.season.astype(int)))
    R = O.first_game_rosters(week1)
    nxt = {(int(s), g): club(t) for s, g, t in zip(R.season, R.gsis_id, R.team)}
    last = {}
    for f in sorted(glob.glob(os.path.join(rosters, 'roster_*.csv'))):
        r = pd.read_csv(f, usecols=['season', 'team', 'gsis_id'], low_memory=False).dropna(subset=['gsis_id'])
        for s, t, g in zip(r.season, r.team, r.gsis_id): last[(int(s), g)] = club(t)
    end = np.zeros(len(S), bool); grp = np.full(len(S), '', object); missing_last = 0
    for i, (k, t, kd) in enumerate(zip(S.key.values, S.t.values, S.kind.values)):
        if kd != 'V' or dyear.get(k) is None or int(t) != dyear[k] + 3: continue
        end[i] = True
        c1, c0 = nxt.get((int(t) + 1, k)), last.get((int(t), k))
        if c0 is None: missing_last += 1
        grp[i] = 'none' if c1 is None else ('kept' if c1 == c0 else 'moved')
    return end, grp, missing_last


def base_value(S, T):
    """Adopted preseason value: offseason matching with games out (docs/DECISION-no-games-in-matching.md)."""
    C.W_V['games'] = 0.0
    pc = O.neighbours_off(S, T)
    look = {int(r): nn for r, nn in zip(pc['test'], pc['nn'][30])}
    T = np.array([r for r in T if int(r) in look], int)                  # early history rows can have too small a pool
    nn_, W_ = [], []
    for r in T:
        nn = look[int(r)]
        assert (S.t.values[nn] <= S.t.values[r] - E.HORIZON).all() and S.key.values[r] not in set(S.key.values[nn])
        w = 0.5 ** ((S.t.values[r] - S.t.values[nn]) / V.HALF_LIFE); nn_.append(nn); W_.append(w / w.sum())
    return T, nn_, W_


def adjust(S, rows, base, y, end, grp, hist_rows, hist_base):
    """Scale end-of-deal rows by their group's out-of-sample history. Returns new predictions and the ratios used."""
    out = base.copy(); used = {}
    ht, hg, hy = S.t.values[hist_rows], grp[hist_rows], y[hist_rows]
    for j, r in enumerate(rows):
        if not end[r]: continue
        t, g = S.t.values[r], grp[r]
        m = (ht <= t - E.HORIZON) & (hg == g)
        assert not (S.key.values[hist_rows][m] == S.key.values[r]).any()
        if m.sum() < N_MIN or hist_base[m].sum() <= 0: continue
        k = hy[m].sum() / hist_base[m].sum(); out[j] = base[j] * k; used.setdefault((int(t), g), round(float(k), 3))
    return out, used


def q(S, rows, p_new, p_old, yt, mask, n_perm=E.N_PERM):
    cl = S.key.values[rows]
    lift, p = C.perm_test(yt[mask], p_new[mask], p_old[mask], cl[mask], n_perm)
    lift_all = 1 - C.rmse(p_new, yt) / C.rmse(p_old, yt)
    return {'end_rows': int(mask.sum()), 'lift': float(lift), 'p': float(p), 'all_lift': float(lift_all),
            'pass': bool(lift >= LIFT_BAR and p < ALPHA and lift_all >= ALL_GUARD)}


def main():
    ap = argparse.ArgumentParser()
    for k in ('nflverse', 'rosters', 'week1'): ap.add_argument('--' + k, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--counts-only', action='store_true'); g.add_argument('--crash', action='store_true'); g.add_argument('--run', action='store_true')
    ap.add_argument('--runs', type=int, default=200)
    a = ap.parse_args()
    st, S, pre, nn2, W2, nn3, W3, counts = O.setup(a.nflverse, a.rosters, a.week1)
    T = pre['test']; y = S.FV.values.astype(float)
    end, grp, miss = groups(S, a.nflverse, a.rosters, a.week1)
    H = np.array([r for r in np.where(end)[0] if E.HORIZON + C.SNAP_FIRST <= S.t.values[r] <= E.TEST[1] - E.HORIZON
                  and S.complete.values[r]], int)                         # history rows: results in by the last test season
    Hset = set(H.tolist())
    allrows = np.array(sorted(set(T.tolist()) | Hset), int)
    allrows, nn_, W_ = base_value(S, allrows)
    assert set(T.tolist()) <= set(allrows.tolist()), 'a test row lost its matches'
    H = np.array([r for r in H if r in set(allrows.tolist())], int)
    ix = {int(r): j for j, r in enumerate(allrows)}
    Tj, Hj = np.array([ix[int(r)] for r in T]), np.array([ix[int(r)] for r in H])
    mask = end[T]
    c = {'test_rows': int(len(T)), 'end_of_deal_test_rows': int(mask.sum()),
         'by_group_test': pd.Series(grp[T][mask]).value_counts().to_dict(),
         'by_position_test': pd.Series(S.pos.values[T][mask]).value_counts().to_dict(),
         'history_rows': int(len(H)), 'history_by_group': pd.Series(grp[H]).value_counts().to_dict(),
         'history_seasons': [int(S.t.values[H].min()), int(S.t.values[H].max())], 'no_last_club_listing': int(miss)}
    print(json.dumps(c, indent=1), flush=True)
    if a.counts_only: return

    def both(yv):
        pa = E.preds(nn_, W_, yv)
        pn, used = adjust(S, T, pa[Tj], yv, end, grp, H, pa[Hj])
        return pa[Tj], pn, used

    if a.crash:
        rng = np.random.default_rng(7); res = {'counts': c}; ok = []
        for i in range(20):
            yn = y.copy()
            for _, gg in pd.DataFrame({'p': S.pos.values, 't': S.t.values}).groupby(['p', 't']).groups.items():
                gg = np.array(list(gg)); yn[gg] = y[rng.permutation(gg)]
            pl, pe, _ = both(yn); ok.append(q(S, T, pe, pl, yn[T], mask, 1000)['pass'])
        res['noise'] = {'runs': 20, 'passed': int(sum(ok)), 'ok': sum(ok) <= 1}; print('noise', res['noise'], flush=True)
        pl, pe, _ = both(y); resid = y[T] - pl; pos = S.pos.values[T]
        for w, n, key in ((0.75, a.runs, 'planted_0.75'), (0.6, max(20, a.runs // 4), 'planted_0.6')):
            rng = np.random.default_rng(int(w * 100)); k = 0; lifts = []
            for i in range(n):
                e = resid.copy()
                for ps in C.POS:
                    m = np.where(pos == ps)[0]; e[m] = resid[rng.permutation(m)]
                truth = np.maximum(0.0, pl + w * (pe - pl) + e)
                r = q(S, T, pe, pl, truth, mask, 1000); k += r['pass']; lifts.append(r['lift'])
            res[key] = {'runs': n, 'passed': int(k), 'share': k / n, 'median_lift': float(np.median(lifts))}
            if w == 0.75: res[key]['ok'] = k / n >= 0.80
            print(key, res[key], flush=True)
        json.dump(res, open(os.path.join(OUT, 'ovs_second_contract_crash.json'), 'w'), indent=1, default=float)
        print('crash tests:', 'PASS' if res['noise']['ok'] and res['planted_0.75']['ok'] else 'FAIL'); return

    pl, pe, used = both(y); yt = y[T]
    res = {'prereg': 'docs/PREREG-ovs-second-contract.md', 'counts': c, 'Q': q(S, T, pe, pl, yt, mask),
           'trades': E.q2(S, pre, pe, pl, yt),
           'ratios_used': {f'{t} {g}': v for (t, g), v in sorted(used.items())},
           'by_group_produced_over_base': {g: float(yt[mask & (grp[T] == g)].sum() / pl[mask & (grp[T] == g)].sum())
                                           for g in ('kept', 'moved', 'none')}}
    res['decision'] = 'scale end-of-deal values by group history' if res['Q']['pass'] and res['trades']['guard_ok'] else 'no contract-moment adjustment'
    json.dump(res, open(os.path.join(OUT, 'ovs_second_contract_results.json'), 'w'), indent=1, default=float)
    print(json.dumps({k: res[k] for k in ('Q', 'trades', 'ratios_used', 'by_group_produced_over_base', 'decision')}, indent=1, default=float))


if __name__ == '__main__':
    main()
